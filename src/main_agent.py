from typing import Dict, List, Literal, Optional
from langgraph.graph import StateGraph, MessagesState, START, END

from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv       
from llm_factory import get_llm_with_tools
from prompts.decompose import *  
 
from pydantic import BaseModel, Field  
 
import os
import json 
load_dotenv()

class State(MessagesState): 
    next: str 
    predicates: Optional[List[Dict[str, str]]]
    predicate_type_dict: Optional[List[Dict[str, str]]]
    verifiable_subclaims: Optional[List[str]]
  
class FactAgent:
    def __init__(self, dataset: str, model_name = None, temperature: float = 0.2):

        """
        Initialize the FactAgent with specified model and temperature.
        
        Args:
            model_name: The model to use
            temperature: The temperature for the model (default: 0.2)
        """
        self.dataset = dataset 
        provider = os.getenv("LLM_PROVIDER")
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_PROVIDER_BASE_URL")

        self.llm = get_llm_with_tools(
            [], # No tools for now, but we can add them later as needed
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key,
        )
        self.llm_no_tools = get_llm_with_tools(
            [],
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key,
            allow_tools=False, 
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
        self.decomposition_llm = self.llm_no_tools.with_structured_output(
            claim_decomposition, method="function_calling"
        )
        self.classification_llm = self.llm_no_tools.with_structured_output(
            claim_classification, method="function_calling"
        )
        self.splitter_llm = self.llm_no_tools.with_structured_output(
            claim_splitting, method="function_calling"
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
            return Command(
                update={
                    "predicates": predicates,
                    "messages": [
                        HumanMessage(content=str(predicates), name="claim_decomposition")
                    ] # Update the state with the subclaims extracted by the decomposer agent. We add a new message to the conversation with the content being the subclaims and the name "claim_decomposition" to indicate which agent produced this message.
                },
                goto="claim_classification",
            )
        
        def claim_classification_node(state: State) -> Command[Literal["claim_splitter"]]:
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
                goto="claim_splitter",
            )

        def claim_splitter_node(state: State) -> Command[Literal["__end__"]]:
            print("[claim_splitter] start")
            predicate_type_dict = state.get("predicate_type_dict") or []
            verifiable_subclaims = [
                item.get("predicate")
                for item in predicate_type_dict
                if isinstance(item, dict) and item.get("type") == "verifiable"
            ]
            print("[claim_splitter] filter complete")
            return Command(
                update={
                    "verifiable_subclaims": verifiable_subclaims,
                    "messages": [
                        HumanMessage(content=str(verifiable_subclaims), name="claim_filter")
                    ]
                },
                goto=END,
            )
        
        input_ingester = StateGraph(State)
        input_ingester.add_node("claim_decomposition", claim_decomposition_node)
        input_ingester.add_node("claim_classification", claim_classification_node)
        input_ingester.add_node("claim_splitter", claim_splitter_node)
        input_ingester.add_edge(START, "claim_decomposition")
        input_ingester.add_edge("claim_decomposition", "claim_classification")
        input_ingester.add_edge("claim_classification", "claim_splitter")
        
        self.ingestion_graph = input_ingester.compile()


    def _build_main_graph(self):
        """Build the main workflow graph."""
        def call_input_ingestion_team(state: State) -> Command[Literal["supervisor"]]:
            response = self.ingestion_graph.invoke({"messages": state["messages"][-1]})
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=response["messages"][-1].content, name="input_ingestor"
                        )
                    ]
                },
                goto="supervisor",
            )

        def query_generation_node(state: State) -> Command[Literal["supervisor"]]:
            result = self.query_generation_agent.invoke(state)
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=str(result["structured_response"]["subclaim_with_questions"]), name="query_generator")
                    ]
                },
                goto="supervisor",
            )

        def evidence_seeking_node(state: State) -> Command[Literal["supervisor"]]:
            result = self.evidence_seeking_agent.invoke(state)
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=str(result["structured_response"]["subclaims_with_query_evidence"]), name="evidence_seeker")
                    ]
                },
                goto="supervisor",
            )

        def verdict_prediction_node(state: State) -> Command[Literal["supervisor"]]:
            result = self.verdict_prediction_agent.invoke(state)
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=str(result["structured_response"]["result"]), name="verdict_predictor")
                    ]
                },
                goto="supervisor",
            )

        orchestrator = self._make_supervisor_node(["input_ingestor", "query_generator", "evidence_seeker", "verdict_predictor"])
        
        super_builder = StateGraph(State)
        super_builder.add_node("supervisor", orchestrator)
        super_builder.add_node("input_ingestor", call_input_ingestion_team)
        super_builder.add_node("query_generator", query_generation_node)
        super_builder.add_node("evidence_seeker", evidence_seeking_node)
        super_builder.add_node("verdict_predictor", verdict_prediction_node)
        super_builder.add_edge(START, "supervisor")
        
        self.super_graph = super_builder.compile()
    
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
        for step in self.ingestion_graph.stream(
            {"messages": messages},
            {"recursion_limit": recursion_limit}
        ):
            if verbose:
                print(step)
                print("---")
            results.append(step)
        print("[process_claim] graph stream finished")
        
        return results
    
    
    def process_multiple_claims(self, claims: list[str], recursion_limit: int = 150, verbose: bool = False):
        """
        Process multiple claims through the fact-checking pipeline.
        
        Args:
            claims: List of claims to fact-check
            recursion_limit: Maximum number of recursions allowed (default: 150)
            verbose: Whether to print intermediate steps (default: False)
        
        Returns:
            list: Results for each claim
        """
        results = []
        for i, claim in enumerate(claims):
            if verbose:
                print(f"\n=== Processing Claim {i+1}/{len(claims)} ===")
                print(f"Claim: {claim}")
                print("=" * 50)
            
            result = self.process_claim(claim, recursion_limit, verbose)
            result = json.loads(result)
            results.append({
                "claim": claim,
                "label": result["label"],
                "explanation": result["explanation"]
            })
        
        return results


if __name__ == "__main__":
    agent = FactAgent(dataset="covid19_claims")  
    claim = "Taking a daily vitamin D supplement helps prevent osteoporosis in postmenopausal women, but it should be avoided by those with kidney stones to prevent worsening nephrolithiasis."
    #claim = "The continuous use of a wearable AI-powered glucose monitoring system improves long-term metabolic health outcomes in adults with Type 2 Diabetes by improving daily glucose stability, increasing adherence to treatment plans, and reducing diabetes-related complications."
    claim = "il fumo causa cancro, forse è meglio non fumare"
    result = agent.process_claim(claim, verbose=True, recursion_limit=10)  # Set a reasonable recursion limit for testing
    print("\nFinal Result:")
    print(result)
    