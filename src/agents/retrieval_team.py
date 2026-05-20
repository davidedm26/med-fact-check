import json
import ast
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.retrieve import retriever_agent_prompt, unified_retriever_prompt
from tools.retrieve.download import (
    download_from_clinical_trials,
    download_from_kb,
    download_from_literature,
)
from tools.retrieve.sparse import sparse_retrieve_tool

def build_retrieval_graph(retriever_llm):
    """Build the unified retrieval subgraph."""

    RETRIEVAL_STRATEGY_TO_NODE = {
        "sparse": "sparse_retriever",
    }

    def _select_download_tool(tool_name: str):
        if tool_name == download_from_clinical_trials.name:
            return download_from_clinical_trials, "clinical_trials"
        if tool_name == download_from_kb.name:
            return download_from_kb, "knowledge_base"
        return download_from_literature, "literature"

    def _normalize_search_queries(value, fallback_query: str):
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

    def downloader_agent_node(state: State):
        print("[downloader_agent] start")
        query = _message_text(state["messages"][-1])
        subclaim_id = state.get("subclaim_id") or "sub_01"

        compiled_prompt = retriever_agent_prompt.replace("{sub_claim_text}", query)
        messages = [
            SystemMessage(content=unified_retriever_prompt),
            HumanMessage(content=compiled_prompt)
        ]

        print("[downloader_agent] invoking unified llm")
        response = retriever_llm.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []

        selected_tool = download_from_literature
        selected_source = "literature"
        search_queries = [query]

        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            if tool_name in {
                download_from_literature.name,
                download_from_clinical_trials.name,
                download_from_kb.name,
            }:
                selected_tool, selected_source = _select_download_tool(tool_name)
                tool_args = tool_call.get("args", {})
                search_queries = _normalize_search_queries(tool_args.get("search_queries"), query)
                break

        print(f"[downloader_agent] downloading from {selected_source} with args: {search_queries}")
        downloaded_documents = selected_tool.invoke({"sub_id": subclaim_id, "search_queries": search_queries})

        return {
            "retrieval_source": selected_source,
            "retrieval_query": search_queries[0],
            "downloaded_documents": downloaded_documents,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_source": selected_source,
                        "retrieval_query": search_queries[0],
                        "subclaim_id": subclaim_id,
                        "downloaded_documents_count": len(downloaded_documents),
                    }),
                    name="downloader_agent",
                )
            ],
        }

    def retrieval_strategy_router_node(state: State):
        print("[retrieval_strategy_router] start")
        query = state.get("retrieval_query") or _message_text(state["messages"][-1])
        retrieval_strategy = "sparse"
        print(f"[retrieval_strategy_router] selected {retrieval_strategy}")
        return {
            "retrieval_strategy": retrieval_strategy,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_query": query,
                        "retrieval_strategy": retrieval_strategy,
                    }),
                    name="retrieval_strategy_router",
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

    retrieval_builder = StateGraph(State)
    retrieval_builder.add_node("downloader_agent", downloader_agent_node)
    retrieval_builder.add_node("retrieval_strategy_router", retrieval_strategy_router_node)
    retrieval_builder.add_node("sparse_retriever", sparse_retriever_node)

    retrieval_builder.add_edge(START, "downloader_agent")
    retrieval_builder.add_edge("downloader_agent", "retrieval_strategy_router")

    def route_retrieval_strategy(state: State):
        strategy = state.get("retrieval_strategy") or "sparse"
        return RETRIEVAL_STRATEGY_TO_NODE.get(strategy, "sparse_retriever")

    retrieval_builder.add_conditional_edges("retrieval_strategy_router", route_retrieval_strategy)
    retrieval_builder.add_edge("sparse_retriever", END)

    return retrieval_builder.compile()
