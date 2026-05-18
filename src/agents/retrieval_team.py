import json
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from state import State, _message_text
from prompts.retriever_agent_prompt import retriever_agent_prompt
from prompts.retrieve import unified_retriever_prompt
from tools.retrieve.download_tool import download_documents
from tools.retrieve.sparse_retrieve_tool import sparse_retrieve_tool
from tools.retrieve.dense_retrieve_tool import dense_retrieve_tool

def build_retrieval_graph(retriever_llm):
    """Build the unified retrieval subgraph."""

    def retriever_agent_node(state: State):
        print("[retriever_agent] start")
        query = _message_text(state["messages"][-1])
        documents = state.get("downloaded_documents") or []
        docs_json = json.dumps(documents)

        # We merge M2's context extraction instructions directly
        compiled_prompt = retriever_agent_prompt.replace("{sub_claim_text}", query)

        messages = [
            SystemMessage(content=unified_retriever_prompt),
            HumanMessage(content=compiled_prompt)
        ]

        print("[retriever_agent] invoking unified llm")
        response = retriever_llm.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []

        normalized_query = query
        selected_source = state.get("retrieval_source", "literature")
        downloaded = state.get("downloaded_documents")
        sparse_chunks = state.get("sparse_top_k_chunks", [])
        dense_chunks = state.get("dense_top_k_chunks", [])

        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})

                if tool_name == download_documents.name:
                    selected_source = tool_args.get("target_source", "literature")
                    search_queries = tool_args.get("search_queries", [query])
                    if search_queries:
                         normalized_query = search_queries[0]
                    print(f"[retriever_agent] downloading with args: {tool_args}")
                    downloaded = download_documents.invoke(tool_args)
                    docs_json = json.dumps(downloaded)

                elif tool_name == sparse_retrieve_tool.name:
                    if "documents" not in tool_args or not tool_args["documents"]:
                        tool_args["documents"] = docs_json
                    print(f"[retriever_agent] sparse extracting with args: {tool_args.get('query')}")
                    sparse_chunks = sparse_retrieve_tool.invoke(tool_args)

                elif tool_name == dense_retrieve_tool.name:
                    if "documents" not in tool_args or not tool_args["documents"]:
                        tool_args["documents"] = docs_json
                    print(f"[retriever_agent] dense extracting with args: {tool_args.get('query')}")
                    dense_chunks = dense_retrieve_tool.invoke(tool_args)

        else:
            print("[retriever_agent] fallback: no valid tool call, running default sequence")
            sub_id = "sub_01"
            dl_args = {"sub_id": sub_id, "search_queries": [query], "target_source": "literature"}
            downloaded = download_documents.invoke(dl_args)

            docs_json = json.dumps(downloaded)
            retr_args = {"query": query, "documents": docs_json, "top_k": 3}
            sparse_chunks = sparse_retrieve_tool.invoke(retr_args)
            dense_chunks = dense_retrieve_tool.invoke(retr_args)

        print("[retriever_agent] complete")
        return {
            "retrieval_query": normalized_query,
            "retrieval_source": selected_source,
            "downloaded_documents": downloaded,
            "sparse_top_k_chunks": sparse_chunks,
            "dense_top_k_chunks": dense_chunks
        }

    retrieval_builder = StateGraph(State)
    retrieval_builder.add_node("retriever_agent", retriever_agent_node)

    retrieval_builder.add_edge(START, "retriever_agent")
    retrieval_builder.add_edge("retriever_agent", END)

    return retrieval_builder.compile()
