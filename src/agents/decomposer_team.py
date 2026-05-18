import json
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.decompose import claim_decomposition_prompt, claim_classification_prompt

def build_decomposer_graph(decomposition_llm, classification_llm):
    """Build the input ingestion subgraph for decomposer logic."""

    def claim_decomposition_node(state: State) -> Command[Literal["claim_classification"]]:
        print("[claim_decomposition] start")
        messages = [SystemMessage(content=claim_decomposition_prompt)] + state["messages"]
        structured = decomposition_llm.invoke(messages)
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
        structured = classification_llm.invoke(messages)
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

    return input_ingester.compile()
