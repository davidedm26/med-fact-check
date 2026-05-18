from typing import Annotated, Dict, List, Literal, Optional
from langgraph.graph import StateGraph, MessagesState, START, END

from langgraph.types import Command, Send
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv       
from llm_factory import get_llm_with_tools
from prompts.decompose import *  
from prompts.retrieve import retrieval_downloader_prompt
from tools.retrieve.mock_retrieve import (
    download_documents_for_source,
    download_guidelines_documents,
    download_news_documents,
    download_pubmed_documents,
    download_wikipedia_documents,
    dense_retrieve_chunks,
    sparse_retrieve_chunks,
)
 
from pydantic import BaseModel, Field  
 
import os
import json 
import operator
load_dotenv()


def _message_text(message):
    if hasattr(message, "content"):
        return message.content
    if isinstance(message, (tuple, list)) and len(message) > 1:
        return message[1]
    return str(message)

class State(MessagesState): 
    next: str 
    predicates: Optional[List[Dict[str, str]]]
    predicate_type_dict: Optional[List[Dict[str, str]]]
    verifiable_subclaims: Optional[List[str]]
    subclaim_results: Annotated[List[Dict[str, object]], operator.add]
    retrieval_query: Optional[str]
    retrieval_source: Optional[str]
    downloaded_documents: Optional[List[Dict[str, object]]]
    sparse_top_k_chunks: Optional[List[Dict[str, object]]]
    dense_top_k_chunks: Optional[List[Dict[str, object]]]
  
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
            " If a message with name 'claim_filter' is already present, respond with FINISH."
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
            response = self.llm.with_structured_output(Router, method="function_calling").invoke(messages) # Use JSON mode to avoid tool-calling for router output.
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
        
        self.retrieval_downloader_llm = get_llm_with_tools(
            [
                download_wikipedia_documents,
                download_pubmed_documents,
                download_news_documents,
                download_guidelines_documents,
            ],
            provider=self.provider,
            model_name=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url,
            api_key=self.api_key,
        )
        """
        # Main workflow agents
        self.query_generation_agent = create_agent(
            self.llm, tools=[], system_prompt=claim_decomposition_prompt, response_format=query_generation
        )
        self.evidence_seeking_agent = create_agent(
            self.llm, tools=[search_retrieve_news], system_prompt=evidence_seeking_prompt, response_format=evidence_seeking
        )
        self.verdict_prediction_agent = create_agent(
            self.llm, tools=[], system_prompt=verdict_prediction_prompt, response_format=verdict_prediction
        )
        """
    
    def _build_graphs(self):
        """Build the state graphs for the workflow."""
        # Input ingestion subgraph
        self._build_input_ingestion_graph()
        # Main workflow graph
        self._build_main_graph()
    
    def _build_input_ingestion_graph(self):
        """Build the input ingestion subgraph."""

        def claim_decomposition_node(state: State) -> Command[Literal["claim_classification"]]:
            print("[claim_decomposition] start")
            messages = [SystemMessage(content=claim_decomposition_prompt)] + state["messages"]
            structured = self.decomposition_llm.invoke(messages)
            print("[claim_decomposition] agent response received")

            predicates = structured.get("predicates") if isinstance(structured, dict) else None
            if predicates is None: # if the decomposition agent fails to produce valid output, we can default to treating the entire claim as a single predicate to avoid breaking the workflow. This is a simple fallback strategy to ensure robustness.
                print("Decomposition agent failed to produce valid output. Defaulting to treating the entire claim as a single predicate.")
                predicates = [{"predicate": _message_text(state["messages"][-1])}]  # Use the original claim as the only predicate if decomposition fails
                
            return Command(
                update={
                    "predicates": predicates,
                    "messages": [
                        HumanMessage(content=str(predicates), name="claim_decomposition")
                    ] # Update the state with the subclaims extracted by the decomposer agent. We add a new message to the conversation with the content being the subclaims and the name "claim_decomposition" to indicate which agent produced this message.
                },
                goto="claim_classification",
            )
        
        def claim_classification_node(state: State) -> Command[Literal["claim_filter"]]:
            print("[claim_classification] start")
            predicates = state.get("predicates") or []
            messages = [
                SystemMessage(content=claim_classification_prompt),
                HumanMessage(content=json.dumps(predicates, ensure_ascii=False)),
            ]
            structured = self.classification_llm.invoke(messages)
            print("[claim_classification] agent response received")
            predicate_type_dict = (
                structured.get("predicate_type_dict") if isinstance(structured, dict) else None
            )
            return Command(
                update={
                    "predicate_type_dict": predicate_type_dict,
                    "messages": [
                        HumanMessage(content=str(predicate_type_dict), name="claim_classification")
                    ]
                },
                goto="claim_filter",
            )

        # The claim splitter node is not an LLM agent - it just filters the subclaims based on the classification results and prepares the final list of verifiable subclaims for the main workflow.

        def claim_filter_node(state: State) -> Command[Literal["__end__"]]:
            print("[claim_filter] start")
            predicate_type_dict = state.get("predicate_type_dict") or []
            verifiable_subclaims = [
                item.get("predicate")
                for item in predicate_type_dict
                if isinstance(item, dict) and item.get("type") == "verifiable"
            ]
            print("[claim_filter] filter complete")
            return Command(
                update={
                    "verifiable_subclaims": verifiable_subclaims,
                    "messages": [
                        HumanMessage(content=str(verifiable_subclaims), name="claim_filter")
                    ]
                },
                goto=END,
            )
        
        # The injestion graph is a sequential graph that runs the claim decomposition, classification, and filtering steps in order
        input_ingester = StateGraph(State)
        
        input_ingester.add_node("claim_decomposition", claim_decomposition_node)
        input_ingester.add_node("claim_classification", claim_classification_node)
        input_ingester.add_node("claim_filter", claim_filter_node)

        input_ingester.add_edge(START, "claim_decomposition")
        input_ingester.add_edge("claim_decomposition", "claim_classification")
        input_ingester.add_edge("claim_classification", "claim_filter")
        
        self.ingestion_graph = input_ingester.compile()

    def _build_retrieval_graph(self):
        """Build the retrieval subgraph."""

        def downloader_node(state: State):
            print("[retrieval_downloader] start")
            query = _message_text(state["messages"][-1])
            messages = [
                SystemMessage(content=retrieval_downloader_prompt),
                HumanMessage(content=query),
            ]
            response = self.retrieval_downloader_llm.invoke(messages)
            tool_calls = getattr(response, "tool_calls", None) or []
            documents = None
            selected_source = "pubmed"
            normalized_query = query

            tool_map = {
                download_wikipedia_documents.name: ("wikipedia", download_wikipedia_documents),
                download_pubmed_documents.name: ("pubmed", download_pubmed_documents),
                download_news_documents.name: ("news", download_news_documents),
                download_guidelines_documents.name: ("guidelines", download_guidelines_documents),
            }

            if tool_calls:
                first_call = tool_calls[0]
                tool_name = first_call.get("name")
                tool_args = first_call.get("args", {})
                if tool_name in tool_map:
                    selected_source, tool_object = tool_map[tool_name]
                    normalized_query = tool_args.get("query") or query
                    documents = tool_object.invoke(tool_args)

            if documents is None:
                documents = download_documents_for_source(selected_source, normalized_query, limit=4)

            print(f"[retrieval_downloader] selected source: {selected_source}")
            return {
                "retrieval_query": normalized_query,
                "retrieval_source": selected_source,
                "downloaded_documents": documents,
            }

        def sparse_retriever_node(state: State):
            print("[sparse_retriever] start")
            query = state.get("retrieval_query") or _message_text(state["messages"][-1])
            documents = state.get("downloaded_documents") or []
            chunks = sparse_retrieve_chunks(documents, query, top_k=3)
            print("[sparse_retriever] top chunks ready")
            return {"sparse_top_k_chunks": chunks}

        def dense_retriever_node(state: State):
            print("[dense_retriever] start")
            query = state.get("retrieval_query") or _message_text(state["messages"][-1])
            documents = state.get("downloaded_documents") or []
            chunks = dense_retrieve_chunks(documents, query, top_k=3)
            print("[dense_retriever] top chunks ready")
            return {"dense_top_k_chunks": chunks}

        retrieval_builder = StateGraph(State)
        retrieval_builder.add_node("download_documents", downloader_node)
        retrieval_builder.add_node("sparse_retriever", sparse_retriever_node)
        retrieval_builder.add_node("dense_retriever", dense_retriever_node)

        retrieval_builder.add_edge(START, "download_documents")
        retrieval_builder.add_edge("download_documents", "sparse_retriever")
        retrieval_builder.add_edge("download_documents", "dense_retriever")
        retrieval_builder.add_edge("sparse_retriever", END)
        retrieval_builder.add_edge("dense_retriever", END)

        self.retrieval_graph = retrieval_builder.compile()

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

        def route_subclaims(state: State):
            subclaims = state.get("verifiable_subclaims") or []
            if not subclaims:
                return END
            return [
                Send(
                    "retrieve_subclaim",
                    {
                        "subclaim": subclaim,
                        "messages": [HumanMessage(content=subclaim, name="subclaim")],
                    },
                )
                for subclaim in subclaims
            ]

        def retrieve_subclaim_node(state: State):
            subclaim = state.get("subclaim") or _message_text(state["messages"][-1])
            response = self.retrieval_graph.invoke({"messages": [("user", subclaim)]})
            retrieval_summary = {
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
        main_builder.add_conditional_edges("input_ingestor", route_subclaims)

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
    