import json
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.decompose import claim_decomposition_prompt, claim_classification_prompt
from utils.logger import get_logger
from utils.mongo_logger import log_node

log = get_logger("DecomposingTeam")
# TO DO: Managing of error cases and fallback mechanisms in case the decomposition or classification agents fail to produce valid output.

def build_decompose_graph(decomposition_agent, classification_agent):
    """Build the input ingestion subgraph for decomposer logic."""

    @log_node("decompose")
    def claim_decomposition_node(state: State) -> Command[Literal["claim_classification"]]: #hardcoded goto for simplicity since the decomposition step always goes to classification next

        log.info("claim_decomposition start")

        messages = [SystemMessage(content=claim_decomposition_prompt)] + state["messages"] # Pass the proper System Prompt along with the conversation history to the decomposition agent. The message should include the original claim that needs to be decomposed, which is typically the last message in the conversation history at this point. 
        structured = decomposition_agent.invoke(messages) 
        log.info("claim_decomposition agent response received")
        log.debug(f"claim_decomposition agent response received: {structured}")

        predicates = structured.get("predicates") if isinstance(structured, dict) else None

        if predicates is None: # if the decomposition agent fails to produce valid output
            pass # TO DO

        return Command(
            update={
                "predicates": predicates,
                "messages": [
                    HumanMessage(content=str(predicates), name="claim_decomposition")
                ] # Update the state with the subclaims extracted by the decomposer agent. We add a new message to the conversation with the content being the subclaims and the name "claim_decomposition" to indicate which agent produced this message.
            },
            goto="claim_classification", # The only edge is to the classification node, so we could avoid this field but we keep it for clarity and consistency with the other nodes.
        )

    @log_node("decompose")
    def claim_classification_node(state: State) -> Command[Literal["claim_filter"]]:
        log.info("claim_classification start")
        predicates = state.get("predicates") or []
        # Pass only natural language queries to the classification agent
        raw_queries = [
            p.get("search_query") or " ".join(str(p.get(k, "")) for k in ("relation", "subject", "object")).strip()
            for p in predicates if isinstance(p, dict)
        ]
        
        queries = []
        for q in raw_queries:
            if q and q not in queries:
                queries.append(q)
                
        if not queries:
            log.info("No queries to classify; skipping classification agent.")
            return Command(
                update={"predicate_type_dict": []},
                goto="claim_filter",
            )
        messages = [
            SystemMessage(content=claim_classification_prompt),
            HumanMessage(content=json.dumps(queries, ensure_ascii=False)), # pass the extracted queries
        ]
        structured = classification_agent.invoke(messages)
        log.info("claim_classification agent response received")
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

    # The claim splitter node doesn't leverage any LLM agent - it just filters the subclaims based on the classification results and prepares the final list of verifiable subclaims for the main workflow.

    @log_node("decompose")
    def claim_filter_node(state: State) -> Command[Literal["__end__"]]:
        log.info("claim_filter start")
        predicate_type_dict = state.get("predicate_type_dict") or []
        verifiable_subclaims = [
            item.get("query")
            for item in predicate_type_dict
            if isinstance(item, dict) and str(item.get("type")).strip().lower() == "verifiable" and item.get("query")
        ]
        log.info("claim_filter complete")
        return Command(
            update={
                "verifiable_subclaims": verifiable_subclaims,
                "messages": [
                    HumanMessage(content=str(verifiable_subclaims), name="claim_filter")
                ]
            },
            goto=END,
        )

    # The decompose graph is a sequential graph that runs the claim decomposition, classification, and filtering steps in order
    decompose_graph = StateGraph(State)

    decompose_graph.add_node("claim_decomposition", claim_decomposition_node)
    decompose_graph.add_node("claim_classification", claim_classification_node)
    decompose_graph.add_node("claim_filter", claim_filter_node)

    decompose_graph.add_edge(START, "claim_decomposition")
    decompose_graph.add_edge("claim_decomposition", "claim_classification")
    decompose_graph.add_edge("claim_classification", "claim_filter")

    return decompose_graph.compile()
