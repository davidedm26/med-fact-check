import json
import ast
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.retrieve import (
    retrieval_source_selection_prompt,
    retrieval_query_generation_prompt,
    retrieval_strategy_router_prompt,
)
from tools.retrieve.download import (
    download_documents,
)
from tools.retrieve.dense import dense_retrieve_tool
from tools.retrieve.sparse import sparse_retrieve_tool

def build_retrieval_graph(source_selector_llm, query_generator_llm, strategy_router_llm):
    """Build the unified retrieval subgraph."""

    RETRIEVAL_STRATEGY_TO_NODE = {
        "sparse": "sparse_retriever",
        "dense": "dense_retriever",
    }

    VALID_TARGET_SOURCES = {"clinical_trials", "knowledge_base", "literature"}

    def _normalize_search_queries(value, fallback_query: str): 
        '''
        Normalize the search queries to ensure we have a list of valid queries, applying fallbacks as needed.
        '''
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()] or [fallback_query]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return [fallback_query]
            try:
                parsed_value = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                return [stripped]
            if isinstance(parsed_value, list):
                normalized = [str(item) for item in parsed_value if str(item).strip()]
                return normalized or [fallback_query]
            return [str(parsed_value)]
        return [fallback_query]

    def source_selector_node(state: State):
        print("[source_selector] start")
        query = _message_text(state["messages"][-1]) #get last message text (each subclaim will be sent to the retrieval node one at a time, so we can assume the last message contains the subclaim to retrieve for)
        subclaim_id = state.get("subclaim_id") 
        messages = [
            SystemMessage(content=retrieval_source_selection_prompt),
            HumanMessage(content=query)
        ]

        print("[source_selector] invoking llm")
        response = source_selector_llm.invoke(messages)
        selected_source = "literature"
        reasoning = "fallback to literature"
        if isinstance(response, dict):
            selected_source = str(response.get("target_source", "literature")).strip().lower()
            reasoning = str(response.get("reasoning", reasoning))
        else:
            selected_source = str(getattr(response, "target_source", "literature")).strip().lower()
            reasoning = str(getattr(response, "reasoning", reasoning))
        if selected_source not in VALID_TARGET_SOURCES:
            selected_source = "literature"

        print(f"[source_selector] selected {selected_source} ({reasoning})")
        return {
            "retrieval_source": selected_source,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_source": selected_source,
                        "reasoning": reasoning,
                        "subclaim_id": subclaim_id,
                    }),
                    name="source_selector",
                )
            ],
        }

    def downloader_agent_node(state: State):
        print("[downloader_agent] start")
        query = _message_text(state["messages"][-1]) # get last message text (the source selector node adds a message with the selected source and reasoning, but the content of the message is a dict in string format, so we need to parse it to extract the original query if needed for fallback)
        
        subclaim_id = state.get("subclaim_id")
        selected_source = state.get("retrieval_source") or "literature"
        messages = [
            SystemMessage(content=retrieval_query_generation_prompt.format(target_source=selected_source)),
            HumanMessage(content=query)
        ]

        print("[downloader_agent] invoking llm for query generation")
        response = query_generator_llm.invoke(messages)
        generated_queries = []
        reasoning = "fallback to input query"
        if isinstance(response, dict):
            generated_queries = response.get("search_queries") or []
            reasoning = str(response.get("reasoning", reasoning))
        else:
            generated_queries = getattr(response, "search_queries", []) or []
            reasoning = str(getattr(response, "reasoning", reasoning))

        search_queries = _normalize_search_queries(generated_queries, query)

        print(f"[downloader_agent] downloading from {selected_source} with args: {search_queries}")
        downloaded_documents = download_documents.invoke(
            {"sub_id": subclaim_id, "search_queries": search_queries, "target_source": selected_source}
        )

        return {
            "retrieval_source": selected_source,
            "retrieval_query": search_queries[0], # TO DO: we should ideally keep all the generated queries for downstream steps and not just the first one, but for simplicity we keep only the first one for now since that's the one we use for retrieval strategy routing and retrieval.
            "downloaded_documents": downloaded_documents,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_source": selected_source,
                        "retrieval_query": search_queries[0],
                        "subclaim_id": subclaim_id,
                        "reasoning": reasoning,
                        "downloaded_documents_count": len(downloaded_documents),
                    }),
                    name="downloader_agent",
                )
            ],
        }

    def retrieval_strategy_router_node(state: State):
        print("[retrieval_strategy_router] start")
        query = state.get("retrieval_query") or _message_text(state["messages"][-1])
        messages = [
            SystemMessage(content=retrieval_strategy_router_prompt),
            HumanMessage(content=f"Query: {query}"),
        ]

        retrieval_strategy = "dense"
        reasoning = "fallback to dense"
        try:
            response = strategy_router_llm.invoke(messages)
            if isinstance(response, dict):
                candidate_strategy = str(response.get("retrieval_strategy", "sparse")).strip().lower()
                reasoning = str(response.get("reasoning", reasoning))
            else:
                candidate_strategy = str(getattr(response, "retrieval_strategy", "sparse")).strip().lower()
                reasoning = str(getattr(response, "reasoning", reasoning))
            if candidate_strategy in RETRIEVAL_STRATEGY_TO_NODE:
                retrieval_strategy = candidate_strategy
        except Exception as exc:
            print(f"[retrieval_strategy_router] fallback to dense due to: {exc}")

        print(f"[retrieval_strategy_router] selected {retrieval_strategy} ({reasoning})")
        return {
            "retrieval_strategy": retrieval_strategy,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_query": query,
                        "retrieval_strategy": retrieval_strategy,
                        "reasoning": reasoning,
                    }),
                    name="retrieval_strategy_router", # next node
                )
            ],
        }

    def sparse_retriever_node(state: State):
        print("[sparse_retriever] start")
        query = state.get("retrieval_query") or _message_text(state["messages"][-1])
        documents = state.get("downloaded_documents") or []
        docs_json = json.dumps(documents)
        sparse_chunks = sparse_retrieve_tool.invoke({"query": query, "documents": docs_json, "top_k": 3})
        print("[sparse_retriever] complete")
        return {
            "retrieval_strategy": "sparse",
            "sparse_top_k_chunks": sparse_chunks,
            "dense_top_k_chunks": [],
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_query": query,
                        "retrieval_strategy": "sparse",
                        "sparse_top_k_chunks_count": len(sparse_chunks),
                    }),
                    name="sparse_retriever",
                )
            ],
        }

    def dense_retriever_node(state: State):
        print("[dense_retriever] start")
        query = state.get("retrieval_query") or _message_text(state["messages"][-1])
        documents = state.get("downloaded_documents") or []
        docs_json = json.dumps(documents)
        dense_chunks = dense_retrieve_tool.invoke({"query": query, "documents": docs_json, "top_k": 3})
        print("[dense_retriever] complete")
        return {
            "retrieval_strategy": "dense",
            "sparse_top_k_chunks": [],
            "dense_top_k_chunks": dense_chunks,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_query": query,
                        "retrieval_strategy": "dense",
                        "dense_top_k_chunks_count": len(dense_chunks),
                    }),
                    name="dense_retriever",
                )
            ],
        }

    retrieval_builder = StateGraph(State)
    retrieval_builder.add_node("source_selector", source_selector_node)
    retrieval_builder.add_node("downloader_agent", downloader_agent_node)
    retrieval_builder.add_node("retrieval_strategy_router", retrieval_strategy_router_node)
    retrieval_builder.add_node("sparse_retriever", sparse_retriever_node)
    retrieval_builder.add_node("dense_retriever", dense_retriever_node)

    retrieval_builder.add_edge(START, "source_selector")
    retrieval_builder.add_edge("source_selector", "downloader_agent")
    retrieval_builder.add_edge("downloader_agent", "retrieval_strategy_router")

    def route_retrieval_strategy(state: State):
        strategy = state.get("retrieval_strategy") or "dense"
        return RETRIEVAL_STRATEGY_TO_NODE.get(strategy, "dense_retriever")

    retrieval_builder.add_conditional_edges("retrieval_strategy_router", route_retrieval_strategy)
    retrieval_builder.add_edge("sparse_retriever", END)
    retrieval_builder.add_edge("dense_retriever", END)

    return retrieval_builder.compile()
