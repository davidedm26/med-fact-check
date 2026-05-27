from typing import Annotated, Dict, List, Literal, Optional
from langgraph.graph import StateGraph, MessagesState, START, END

from langgraph.types import Command, Send
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv       
from utils.llm_factory import get_llm_with_tools 
from prompts.decompose import *  
from prompts.retrieve import (
    retrieval_source_selection_schema,
    retrieval_query_generation_schema,
    retrieval_strategy_router_schema,
)
from prompts.evaluate import (
    reasoning_schema,
)
from tools.retrieve.download import (
    download_documents,
)
from tools.retrieve.sparse import sparse_retrieve_tool
from tools.retrieve.dense import dense_retrieve_tool
 
from pydantic import BaseModel, Field  
 
import os
import json 
import operator
import uuid
load_dotenv()
from utils.config import config

from state import State, _message_text
from utils.logger import get_logger

log = get_logger("MainAgent")


def _provider_api_key_name(provider: str) -> Optional[str]:
    if provider == "nvidia":
        return "NVIDIA_API_KEY"
    if provider == "google":
        return "GOOGLE_API_KEY"
    if provider == "groq":
        return "GROQ_API_KEY"
    return None
  
class FactAgent:
    def __init__(self, dataset: str):

        """
        Initialize the FactAgent, reading LLM parameters from configuration.
        """
        self.dataset = dataset  # Provide the dataset as part of the agent's context for better grounding in responses (not used in the current implementation but can be useful for future enhancements)
        self.provider = config.get("llm.provider", "google")
        provider_settings = config.get(f"llm.providers.{self.provider}", {})
        self.base_url = provider_settings.get("base_url")
        self.model_name = provider_settings.get("model_name", config.get("llm.model_name", "gemma-4-26b-a4b-it"))
        self.temperature = config.get("llm.temperature", 0.2)

        api_key_name = _provider_api_key_name(self.provider)
        if api_key_name and not os.getenv(api_key_name):
            raise ValueError(
                f"Missing required API key for provider '{self.provider}': set {api_key_name} in your .env"
            )

        # General initialization of the LLM without tools, this instance can be used for agent that don't require tools
        self.base_llm = get_llm_with_tools(
            [], # No tools for now, but we can add them later as needed
            provider=self.provider,
            model_name=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url,
            allow_tools = False,
        )
        self._setup_agents()
        self._build_graphs()
    
    # The supervisor node is not currently used in the workflow, as the routing logic is currently embedded in the main graph, but we keep it here for future use in case we want to implement a more dynamic routing strategy between the different subgraphs.
    def _make_supervisor_node(self, members: list[str]):
        """Create a supervisor node for managing conversation between workers."""
        options = ["FINISH"] + members # We can route to any worker or finish the workflow
        system_prompt = (
            "You are a supervisor tasked with managing a conversation between the"
            f" following workers: {members}. Given the following user request and dataset {self.dataset},"
            " respond with the worker to act next. Each worker will perform a"
            " task and respond with their results and status. When finished,"
            " respond with FINISH."
        )

        class Router(BaseModel):
            """Worker to route to next. If no workers needed, route to FINISH."""
            next: str = Field(
            description=f"The next worker to route to. You MUST choose EXACTLY one of these options: {options}"
        )

        def supervisor_node(state: State) -> Command[str]: 
            """An LLM-based router."""
            log.info("supervisor start")
            messages = [
                {"role": "system", "content": system_prompt},
            ] + state["messages"]
            log.info("supervisor invoking llm")
            response = self.base_llm.with_structured_output(Router, method="function_calling").invoke(messages)
            log.info("supervisor llm response received")
            # Check if the response is valid and extract the router choice
            goto = response.next # Extract the router choice from the response
            if goto not in options:
                goto = "FINISH"  # Default to FINISH if the response is invalid
                log.warning(f"Invalid router choice: {response.next}. Defaulting to FINISH.")

            if goto == "FINISH":
                goto = END
            return Command(goto=goto, update={"next": goto}) # goto is the next worker to route to, update the state with the next worker as well

        return supervisor_node
        
    def _setup_agents(self):
        """Setup all the individual agents."""
        # Input ingestion agents (no tool strategy)

        self.decomposition_agent = self.base_llm.with_structured_output(
            claim_decomposition, method="function_calling"
        )
        self.classification_agent = self.base_llm.with_structured_output(
            claim_classification, method="function_calling"
        )

        self.source_selector_agent = self.base_llm.with_structured_output(
            retrieval_source_selection_schema, method="function_calling"
        )
        self.query_generator_agent = self.base_llm.with_structured_output(
            retrieval_query_generation_schema, method="function_calling"
        )
        self.strategy_router_agent = self.base_llm.with_structured_output(
            retrieval_strategy_router_schema, method="function_calling"
        )

        # ── Evaluation Team agents ──
        self.reasoning_agent = self.base_llm.with_structured_output(
            reasoning_schema, method="function_calling"
        )
        
    def _build_graphs(self):
        """Build the state graphs for the workflow."""
        # Input ingestion subgraph
        self._build_decompose_graph()
        # Retrieval subgraph
        self._build_retrieval_graph()
        # Evaluation subgraph
        self._build_evaluation_graph()
        # Aggregator node
        self._build_aggregator()
        # Main workflow graph (Merges the subgraphs and adds routing logic)
        self._build_main_graph()

        

    
    def _build_decompose_graph(self):
        """Build the claim decomposition subgraph."""
        from stages.decomposing_team import build_decompose_graph
        self.decompose_graph = build_decompose_graph(self.decomposition_agent, self.classification_agent)

    def _build_retrieval_graph(self):
        """Build the retrieval subgraph."""
        from stages.retrieval_team import build_retrieval_graph
        self.retrieval_graph = build_retrieval_graph(
            self.source_selector_agent,
            self.query_generator_agent,
            self.strategy_router_agent,
        )

    def _build_evaluation_graph(self):
        """Build the evaluation subgraph."""
        from stages.evaluation_team import build_evaluation_graph
        self.evaluation_graph = build_evaluation_graph(
            self.reasoning_agent,
        )

    def _build_aggregator(self):
        """Build the aggregator node."""
        from stages.aggregator import build_aggregate_node
        self.aggregate_node = build_aggregate_node()

    def _build_main_graph(self):
        """Build the main workflow graph."""
        # The main graph consider the subgraphs as black boxes and just defines the routing logic between them.

        def decompose_node(state: State): 
            response = self.decompose_graph.invoke({"messages": [state["messages"][-1]]})
            verifiable_subclaims = response.get("verifiable_subclaims") or []
            return {
                "verifiable_subclaims": verifiable_subclaims,
                "messages": [
                    HumanMessage(content=str(verifiable_subclaims), name="decompose_node")
                ],
            }

        # This function routes to the retrieval node for each subclaim if there are any verifiable subclaims, otherwise it ends the workflow.
        def route_subclaims(state: State): 
            subclaims = state.get("verifiable_subclaims") or []
            if not subclaims:
                return END

            def _subclaim_query(subclaim):
                if isinstance(subclaim, dict):
                    return subclaim.get("search_query") or " ".join(
                        str(subclaim.get(field, "")) for field in ("relation", "subject", "object")
                    ).strip()
                return _message_text(subclaim)
            
            # It returns a list of Send commands that will send each subclaim to the verify_subgraph one at a time
            return [
                Send(
                    "verify_subclaim", # this is the node we want to send the subclaim to
                    {
                        "subclaim_id": f"sub_{index + 1:02d}", 
                        "subclaim": _subclaim_query(subclaim),
                        "run_id": state.get("run_id"),
                        "messages": [HumanMessage(content=_subclaim_query(subclaim), name="subclaim")],
                    },
                )
                for index, subclaim in enumerate(subclaims) # Each subclaim will be sent to the verify subgraph
            ]

        def retrieval_node(state: State):
            subclaim = state.get("subclaim") or _message_text(state["messages"][-1])
            subclaim_id = state.get("subclaim_id") 
            response = self.retrieval_graph.invoke({"messages": [("user", subclaim)], "subclaim_id": subclaim_id})
            retrieval_summary = {
                "subclaim_id": subclaim_id,
                "subclaim": subclaim,
                "source": response.get("retrieval_source"),
                "query": response.get("retrieval_query"),
                "sparse_top_k_chunks": response.get("sparse_top_k_chunks", []),
                "dense_top_k_chunks": response.get("dense_top_k_chunks", []),
            }
            return {
                "subclaim_results": [retrieval_summary],
                "messages": [
                    HumanMessage(content=str(retrieval_summary), name="retrieve")
                ],
            }

        # ── Evaluation node ───────────────────────────────────────
        # This node runs as the second step inside the verify_subgraph.
        # Because it's isolated per-subclaim, state["subclaim_results"]
        # will contain only the single result from the preceding retrieval_node.
        def evaluation_node(state: State):
            subclaim_results = state.get("subclaim_results") or []
            if not subclaim_results:
                log.info("no subclaim_results to evaluate")
                return {"evaluation_results": [], "messages": []}

            all_evaluation_results = []
            for result in subclaim_results:
                subclaim_id = result.get("subclaim_id", "")
                subclaim = result.get("subclaim", "")
                log.info(f"evaluating {subclaim_id}: {subclaim[:60]}...")

                # Format evidence chunks for the Reasoning Agent prompt
                chunks = (
                    result.get("sparse_top_k_chunks") or []
                ) + (
                    result.get("dense_top_k_chunks") or []
                )
                evidence_lines = []
                for idx, chunk in enumerate(chunks, 1):
                    if isinstance(chunk, dict):
                        text = chunk.get("text") or chunk.get("content") or json.dumps(chunk)
                        source = chunk.get("source") or chunk.get("id") or "unknown"
                        score = chunk.get("score", "")
                        evidence_lines.append(f"[Chunk {idx} | source={source} | score={score}]\n{text}")
                    else:
                        evidence_lines.append(f"[Chunk {idx}]\n{str(chunk)}")
                evidence_text = "\n\n".join(evidence_lines) if evidence_lines else "(No evidence chunks available.)"

                # Invoke the evaluation subgraph for this subclaim
                eval_response = self.evaluation_graph.invoke({
                    "subclaim_id": subclaim_id,
                    "subclaim": subclaim,
                    "evidence_text": evidence_text,
                    "messages": [HumanMessage(content=subclaim, name="evaluation_input")],
                })

                # Collect the evaluation results from the subgraph response
                eval_results = eval_response.get("evaluation_results") or []
                # Enrich each result with the retrieval metadata
                for er in eval_results:
                    er["source"] = result.get("source")
                    er["query"] = result.get("query")
                    er["chunks_count"] = len(chunks)
                all_evaluation_results.extend(eval_results)

            return {
                "evaluation_results": all_evaluation_results,
                "messages": [
                    HumanMessage(
                        content=str([
                            {"subclaim_id": r.get("subclaim_id"), "label": r.get("label"), "confidence": r.get("confidence")}
                            for r in all_evaluation_results
                        ]),
                        name="evaluate",
                    )
                ],
            }

        # ── Verify Subgraph ──
        # Encapsulates retrieve and evaluate for a single subclaim.
        verify_builder = StateGraph(State)
        verify_builder.add_node("retrieve", retrieval_node)
        verify_builder.add_node("evaluate", evaluation_node)
        verify_builder.add_edge(START, "retrieve")
        verify_builder.add_edge("retrieve", "evaluate")
        verify_builder.add_edge("evaluate", END)
        verify_subgraph = verify_builder.compile()

        def verify_wrapper_node(state: State):
            # Invokes the subgraph in isolation
            res = verify_subgraph.invoke(state)
            # Only return the fields that have reducers (Annotated[..., operator.add])
            # to avoid InvalidUpdateError on concurrent LastValue fields (like subclaim_id)
            return {
                "subclaim_results": res.get("subclaim_results", []),
                "evaluation_results": res.get("evaluation_results", []),
                "messages": res.get("messages", [])
            }

        main_builder = StateGraph(State) 
        main_builder.add_node("decompose", decompose_node)
        main_builder.add_node("verify_subclaim", verify_wrapper_node)
        main_builder.add_node("aggregate", self.aggregate_node)
        
        main_builder.add_edge(START, "decompose")
        main_builder.add_conditional_edges("decompose", route_subclaims) # Fan-out to verify_subgraph
        main_builder.add_edge("verify_subclaim", "aggregate")  # Fan-in
        main_builder.add_edge("aggregate", END)

        self.super_graph = main_builder.compile()

        
    
    def process_claim(self, claim: str, recursion_limit: int = 150, verbose: bool = False):
        """
        Process a single claim through the fact-checking pipeline.
        
        Args:
            claim: The claim to fact-check
            recursion_limit: Maximum number of recursions allowed (default: 150)
            verbose: Whether to print intermediate steps (default: False)
        
        Returns:
            dict: The final result of the fact-checking process
        """
        messages = [("user", claim)]
        run_id = str(uuid.uuid4())
        log.info(f"pipeline run_id: {run_id}")
        
        results = []
        log.info("starting graph stream")
        for step in self.super_graph.stream( # stream method allows us to get intermediate results at each step of the graph execution
            {"messages": messages, "run_id": run_id}, # initial state with the claim as the first user message
            {"recursion_limit": recursion_limit} # recursion limit to prevent infinite loops in case of errors
        ):
            if verbose:
                log.info(f"Step output: {step}")
                print("---")
            results.append(step)
        log.info("graph stream finished")
        
        return results
    



if __name__ == "__main__":
    agent = FactAgent(dataset="covid19_claims")  

    
    #claim = "Taking a daily vitamin D supplement helps prevent osteoporosis in postmenopausal women, but it should be avoided by those with kidney stones to prevent worsening nephrolithiasis."
    #claim = "The continuous use of a wearable AI-powered glucose monitoring system improves long-term metabolic health outcomes in adults with Type 2 Diabetes by improving daily glucose stability, increasing adherence to treatment plans, and reducing diabetes-related complications."
    #claim = "il fumo causa cancro, forse è meglio non fumare"
    #claim = "The use of corticosteroids in the treatment of severe COVID-19 cases reduces mortality rates by mitigating the hyperinflammatory response, but it may increase the risk of secondary infections and should be used with caution in patients with a history of immunosuppression."
    
    # Shorter claim
    claim = "COVID-19 vaccines are effective in preventing severe illness and hospitalization, but their efficacy may wane over time, necessitating booster doses to maintain optimal protection, especially against emerging variants."
    
    
    result = agent.process_claim(claim, verbose=False, recursion_limit=10)  # Set a reasonable recursion limit for testing
    print("\nFinal Result:")
    print(result)
    