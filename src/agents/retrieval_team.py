import json
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.retriever_agent_prompt import retriever_agent_prompt
from prompts.retrieve import retrieval_downloader_prompt, sparse_retriever_prompt, dense_retriever_prompt
from tools.retrieve.download_tool import download_documents
from tools.retrieve.sparse_retrieve_tool import sparse_retrieve_tool
from tools.retrieve.dense_retrieve_tool import dense_retrieve_tool

def build_retrieval_graph(retrieval_downloader_llm, sparse_retriever_llm, dense_retriever_llm):
    """Build the retrieval subgraph for the retrieval team logic."""

    def downloader_node(state: State):
        print("[retrieval_downloader] start")
        query = _message_text(state["messages"][-1])

        # Use the M2 retriever agent prompt for the downloader node
        compiled_prompt = retriever_agent_prompt.replace("{sub_claim_text}", query)
        messages = [
            SystemMessage(content=retrieval_downloader_prompt),
            HumanMessage(content=compiled_prompt),
        ]

        print("[retrieval_downloader] invoking llm")
        response = retrieval_downloader_llm.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        documents = None
        selected_source = "literature"
        normalized_query = query
        sub_id = "sub_01" # In a real scenario, this would be dynamically generated

        if tool_calls:
            first_call = tool_calls[0]
            tool_name = first_call.get("name")
            tool_args = first_call.get("args", {})
            if tool_name == download_documents.name:
                selected_source = tool_args.get("target_source", "literature")
                search_queries = tool_args.get("search_queries", [query])
                if search_queries:
                        normalized_query = search_queries[0]

                # Use the tool object from the module
                print(f"[retrieval_downloader] invoking tool with args: {tool_args}")
                documents = download_documents.invoke(tool_args)

        # Fallback if no tool call was made or it failed
        if documents is None:
            print("[retrieval_downloader] fallback: no valid tool call, using default")
            tool_args = {"sub_id": sub_id, "search_queries": [query], "target_source": "literature"}
            documents = download_documents.invoke(tool_args)

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

        # Serialize documents to string for the tool
        docs_json = json.dumps(documents)

        messages = [
            SystemMessage(content=sparse_retriever_prompt),
            HumanMessage(content=query),
        ]

        print("[sparse_retriever] invoking llm")
        response = sparse_retriever_llm.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        chunks = []

        if tool_calls:
            first_call = tool_calls[0]
            if first_call.get("name") == sparse_retrieve_tool.name:
                tool_args = first_call.get("args", {})
                # Ensure documents are provided to the tool
                if "documents" not in tool_args:
                    tool_args["documents"] = docs_json

                print(f"[sparse_retriever] invoking tool with query: {tool_args.get('query')}")
                chunks = sparse_retrieve_tool.invoke(tool_args)

        if not chunks:
            print("[sparse_retriever] fallback: no valid tool call, using default")
            tool_args = {"query": query, "documents": docs_json, "top_k": 3}
            chunks = sparse_retrieve_tool.invoke(tool_args)

        print("[sparse_retriever] top chunks ready")
        return {"sparse_top_k_chunks": chunks}

    def dense_retriever_node(state: State):
        print("[dense_retriever] start")
        query = state.get("retrieval_query") or _message_text(state["messages"][-1])
        documents = state.get("downloaded_documents") or []

        # Serialize documents to string for the tool
        docs_json = json.dumps(documents)

        messages = [
            SystemMessage(content=dense_retriever_prompt),
            HumanMessage(content=query),
        ]

        print("[dense_retriever] invoking llm")
        response = dense_retriever_llm.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        chunks = []

        if tool_calls:
            first_call = tool_calls[0]
            if first_call.get("name") == dense_retrieve_tool.name:
                tool_args = first_call.get("args", {})
                # Ensure documents are provided to the tool
                if "documents" not in tool_args:
                    tool_args["documents"] = docs_json

                print(f"[dense_retriever] invoking tool with query: {tool_args.get('query')}")
                chunks = dense_retrieve_tool.invoke(tool_args)

        if not chunks:
            print("[dense_retriever] fallback: no valid tool call, using default")
            tool_args = {"query": query, "documents": docs_json, "top_k": 3}
            chunks = dense_retrieve_tool.invoke(tool_args)

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

    return retrieval_builder.compile()
