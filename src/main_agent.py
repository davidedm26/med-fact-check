from typing import Annotated, Dict, List, Literal, Optional
from langgraph.graph import StateGraph, MessagesState, START, END

from langgraph.types import Command, Send
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv       
from llm_factory import get_llm_with_tools 
from prompts.decompose import *  
from tools.retrieve.download import (
    download_documents,
    download_from_clinical_trials,
    download_from_kb,
    download_from_literature,
)
from tools.retrieve.sparse import sparse_retrieve_tool
from tools.retrieve.dense import dense_retrieve_tool
 
from pydantic import BaseModel, Field  
 
import os
import json 
import operator
load_dotenv()


from state import State, _message_text
  
class FactAgent:
    def __init__(self, dataset: str, model_name = None, temperature: float = 0.2):

        """
        Initialize the FactAgent with specified model and temperature.
        
        Args:
            model_name: The model to use
            temperature: The temperature for the model (default: 0.2)
        """
        self.dataset = dataset 
        self.provider = os.getenv("LLM_PROVIDER")
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_PROVIDER_BASE_URL")
        self.model_name = model_name
        self.temperature = temperature

        self.llm = get_llm_with_tools(
            [], # No tools for now, but we can add them later as needed
            provider=self.provider,
            model_name=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url,
            api_key=self.api_key,
        )
        self._setup_agents()
        self._build_graphs()
    
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
            print("[supervisor] start")
            messages = [
                {"role": "system", "content": system_prompt},
            ] + state["messages"]
            print("[supervisor] invoking llm")
            response = self.llm.with_structured_output(Router, method="function_calling").invoke(messages)
            print("[supervisor] llm response received")
            # Check if the response is valid and extract the router choice
            goto = response.next # Extract the router choice from the response
            if goto not in options:
                goto = "FINISH"  # Default to FINISH if the response is invalid
                print(f"Invalid router choice: {response.next}. Defaulting to FINISH.")

            if goto == "FINISH":
                goto = END
            return Command(goto=goto, update={"next": goto}) # goto is the next worker to route to, update the state with the next worker as well

        return supervisor_node
    
    def _setup_agents(self):
        """Setup all the individual agents."""
        # Input ingestion agents (no tool strategy)
        self.decomposition_llm = self.llm.with_structured_output(
            claim_decomposition, method="function_calling"
        )
        self.classification_llm = self.llm.with_structured_output(
            claim_classification, method="function_calling"
        )
        
        self.retriever_llm = get_llm_with_tools(
            [
                download_from_literature,
                download_from_clinical_trials,
                download_from_kb,
                download_documents,
                sparse_retrieve_tool,
                dense_retrieve_tool,
            ],
            provider=self.provider,
            model_name=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url,
            api_key=self.api_key,
        )
    
    def _build_graphs(self):
        """Build the state graphs for the workflow."""
        # Input ingestion subgraph
        self._build_input_ingestion_graph()
        # Retrieval subgraph
        self._build_retrieval_graph()
        # Main workflow graph
        self._build_main_graph()
    
    def _build_input_ingestion_graph(self):
        """Build the input ingestion subgraph."""
        from agents.decomposer_team import build_decomposer_graph
        self.ingestion_graph = build_decomposer_graph(self.decomposition_llm, self.classification_llm)

    def _build_retrieval_graph(self):
        """Build the retrieval subgraph."""
        from agents.retrieval_team import build_retrieval_graph
        self.retrieval_graph = build_retrieval_graph(self.retriever_llm)

    def _build_main_graph(self):
        """Build the main workflow graph."""

        def input_ingestor_node(state: State):
            response = self.ingestion_graph.invoke({"messages": [state["messages"][-1]]})
            verifiable_subclaims = response.get("verifiable_subclaims") or []
            return {
                "verifiable_subclaims": verifiable_subclaims,
                "messages": [
                    HumanMessage(content=str(verifiable_subclaims), name="input_ingestor")
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

            return [
                Send(
                    "retrieve_subclaim",
                    {
                        "subclaim_id": f"sub_{index + 1:02d}",
                        "subclaim": _subclaim_query(subclaim),
                        "messages": [HumanMessage(content=_subclaim_query(subclaim), name="subclaim")],
                    },
                )
                for index, subclaim in enumerate(subclaims) # Each subclaim will be sent to the retrieval node one at a time (check on this)
            ]

        def retrieve_subclaim_node(state: State):
            subclaim = state.get("subclaim") or _message_text(state["messages"][-1])
            subclaim_id = state.get("subclaim_id") or "sub_01"
            response = self.retrieval_graph.invoke({"messages": [("user", subclaim)]})
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
                    HumanMessage(content=str(retrieval_summary), name="retrieve_subclaim")
                ],
            }

        main_builder = StateGraph(State)
        main_builder.add_node("input_ingestor", input_ingestor_node)
        main_builder.add_node("retrieve_subclaim", retrieve_subclaim_node)
        main_builder.add_edge(START, "input_ingestor")
        main_builder.add_conditional_edges("input_ingestor", route_subclaims) # Route to retrieval for each subclaim if there are any, otherwise end the workflow.

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
        
        results = []
        print("[process_claim] starting graph stream")
        for step in self.super_graph.stream(
            {"messages": messages},
            {"recursion_limit": recursion_limit}
        ):
            if verbose:
                print(step)
                print("---")
            results.append(step)
        print("[process_claim] graph stream finished")
        
        return results
    



if __name__ == "__main__":
    agent = FactAgent(dataset="covid19_claims")  
    #claim = "Taking a daily vitamin D supplement helps prevent osteoporosis in postmenopausal women, but it should be avoided by those with kidney stones to prevent worsening nephrolithiasis."
    #claim = "The continuous use of a wearable AI-powered glucose monitoring system improves long-term metabolic health outcomes in adults with Type 2 Diabetes by improving daily glucose stability, increasing adherence to treatment plans, and reducing diabetes-related complications."
    #claim = "il fumo causa cancro, forse è meglio non fumare"
    claim = "The use of corticosteroids in the treatment of severe COVID-19 cases reduces mortality rates by mitigating the hyperinflammatory response, but it may increase the risk of secondary infections and should be used with caution in patients with a history of immunosuppression."
    result = agent.process_claim(claim, verbose=True, recursion_limit=10)  # Set a reasonable recursion limit for testing
    print("\nFinal Result:")
    print(result)
    