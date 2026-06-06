from typing import Annotated, Dict, List, Literal, Optional
from langgraph.graph import StateGraph, MessagesState, START, END

from langgraph.types import Command, Send
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv       
from utils.llm_factory import get_llm_with_tools 
from prompts.decompose import *  
from prompts.retrieve import (
    retrieval_source_selection_schema,
)
from prompts.evaluate import (
    reasoning_schema,
    veracity_schema,
)
from prompts.aggregate import aggregator_schema
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
    def __init__(self):

        """
        Initialize the FactAgent, reading LLM parameters from configuration.
        """
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
             f" following workers: {members}. Given the following user request,"
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
        ).with_retry(stop_after_attempt=5, wait_exponential_jitter=True)
        
        self.classification_agent = self.base_llm.with_structured_output(
            claim_classification, method="function_calling"
        ).with_retry(stop_after_attempt=5, wait_exponential_jitter=True)

        self.source_selector_agent = self.base_llm.with_structured_output(
            retrieval_source_selection_schema, method="function_calling"
        ).with_retry(stop_after_attempt=5, wait_exponential_jitter=True)

        # ── Evaluation Team agents ──
        self.reasoning_agent = self.base_llm.with_structured_output(
            reasoning_schema, method="function_calling"
        ).with_retry(stop_after_attempt=5, wait_exponential_jitter=True)
        
        self.veracity_agent = self.base_llm.with_structured_output(
            veracity_schema, method="function_calling"
        ).with_retry(stop_after_attempt=5, wait_exponential_jitter=True)
        
        # ── Aggregator Agent ──
        self.aggregator_agent = self.base_llm.with_structured_output(
            aggregator_schema, method="function_calling"
        ).with_retry(stop_after_attempt=5, wait_exponential_jitter=True)
        
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
            self.base_llm,
        )

    def _build_evaluation_graph(self):
        """Build the evaluation subgraph."""
        from stages.evaluation_team import build_evaluation_graph
        self.evaluation_graph = build_evaluation_graph(
            self.reasoning_agent,
            self.veracity_agent,
        )

    def _build_aggregator(self):
        """Build the aggregator node."""
        from stages.aggregator import build_aggregate_node
        self.aggregate_node = build_aggregate_node(self.aggregator_agent)

    def _build_main_graph(self):
        """Build the main workflow graph."""
        # The main graph consider the subgraphs as black boxes and just defines the routing logic between them.

        def decompose_node(state: State): 
            response = self.decompose_graph.invoke({
                "messages": [state["messages"][-1]],
                "run_id": state.get("run_id"),
            })
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
            response = self.retrieval_graph.invoke({
                "messages": [("user", subclaim)],
                "subclaim_id": subclaim_id,
                "subclaim": subclaim,
                "run_id": state.get("run_id"),
            })
            retrieval_summary = {
                "subclaim_id": subclaim_id,
                "subclaim": subclaim,
                "source": response.get("retrieval_source"),
                "queries_by_source": response.get("queries_by_source", {}),
                "retrieved_chunks": response.get("retrieved_chunks", []),
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
                chunks = result.get("retrieved_chunks") or []
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
                    "run_id": state.get("run_id"),
                })

                # Collect the evaluation results from the subgraph response
                eval_results = eval_response.get("evaluation_results") or []
                # Enrich each result with the retrieval metadata
                for er in eval_results:
                    er["source"] = result.get("source")
                    er["query"] = result.get("query")
                    er["chunks_count"] = len(chunks)
                    er["retrieved_chunks"] = chunks
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

        
    
    def _clean_step(self, data):
        if isinstance(data, dict):
            return {k: self._clean_step(v) for k, v in data.items() if k != "messages"}
        elif isinstance(data, list):
            return [self._clean_step(item) for item in data]
        return data

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
        
        if not claim or not str(claim).strip():
            log.warning("Empty claim detected. Skipping pipeline execution.")
            return {
                "claim": "",
                "true_label": "nei",
                "predicted_label": "not_enough_information",
                "confidence": 0.0,
                "subclaims": []
            }

        
        # Inject current dataset into global config for retrieval APIs
        current_dataset = getattr(self, "dataset", "scifact")
        config.set("current_dataset", current_dataset)
        
        log.info(f"pipeline run_id: {run_id}")
        
        results = []
        log.info("starting graph stream")
        for step in self.super_graph.stream( # stream method allows us to get intermediate results at each step of the graph execution
            {"messages": messages, "run_id": run_id}, # initial state with the claim as the first user message
            {"recursion_limit": recursion_limit} # recursion limit to prevent infinite loops in case of errors
        ):
            clean_s = self._clean_step(step)
            if verbose:
                log.info(f"Step output: {clean_s}")
                print("---")
            results.append(clean_s)
        
        elapsed = time.perf_counter() - t0
        log.info(f"graph stream finished in {elapsed:.2f}s")
        
        return results

    def stream_claim(self, claim: str, recursion_limit: int = 150):
        """
        Generator that yields each step of the pipeline.
        Strips 'messages' to ensure JSON serialization.
        """
        messages = [("user", claim)]
        run_id = str(uuid.uuid4())
        log.info(f"pipeline stream run_id: {run_id}")
        
        if not claim or not str(claim).strip():
            log.warning("Empty claim detected. Skipping pipeline stream execution.")
            yield {"error": "Claim cannot be empty or whitespace.", "claim": ""}
            return

        for step in self.super_graph.stream(
            {"messages": messages, "run_id": run_id},
            {"recursion_limit": recursion_limit}
        ):
            yield self._clean_step(step)

    



if __name__ == "__main__":
    agent = FactAgent()

    claim_list = [
        "Birth-weight is negatively associated with breast cancer",
        "Autophagy deficiency in the liver increases vulnerability to insulin resistance",
        "Metformin reduces the risk of cardiovascular events in Type 2 Diabetes patients, but it significantly increases the risk of lactic acidosis."
    ]
    
    idx = 2  # Cambia questo indice  per testare un claim diverso
    claim = claim_list[idx]
    
    log.info(f"Testing claim [{idx}/{len(claim_list)-1}]: {claim}")
    
    result = agent.process_claim(claim, verbose=False, recursion_limit=10)  # Set a reasonable recursion limit for testing
    print("\nFinal Result:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False).encode('cp1252', errors='replace').decode('cp1252'))
    