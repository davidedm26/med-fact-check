import json
import ast
import concurrent.futures
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from state import State, _message_text
from prompts.retrieve import (
    retrieval_source_selection_prompt,
    retrieval_query_generation_prompt,
    get_retrieval_query_generation_schema,
)
from tools.retrieve.download import (
    download_documents,
)
from tools.retrieve.dense import dense_retrieve_tool
from tools.retrieve.sparse import sparse_retrieve_tool
from utils.logger import get_logger
from utils.mongo_logger import log_node
from utils.config import config

log = get_logger("RetrievalTeam")

def build_retrieval_graph(source_selector_llm, base_llm):
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

    @log_node("retrieval")
    def source_selector_node(state: State):
        log.info("source_selector start")
        query = state.get("subclaim") or _message_text(state["messages"][0])
        subclaim_id = state.get("subclaim_id") 
        dynamic_coins = config.get("retrieval.dynamic_coins", 3)
        formatted_prompt = retrieval_source_selection_prompt.format(total_coins=dynamic_coins)
        
        messages = [
            SystemMessage(content=formatted_prompt),
            HumanMessage(content=query)
        ]

        log.info("source_selector invoking llm")
        response = source_selector_llm.invoke(messages)
        coins = {"clinical_trials": 0, "knowledge_base": 0, "literature": dynamic_coins}
        reasoning = "fallback to literature"
        
        try:
            if isinstance(response, dict):
                coins["clinical_trials"] = max(0, int(response.get("clinical_trials_coins", 0)))
                coins["knowledge_base"] = max(0, int(response.get("knowledge_base_coins", 0)))
                coins["literature"] = max(0, int(response.get("literature_coins", dynamic_coins)))
                reasoning = str(response.get("reasoning", reasoning))
            else:
                coins["clinical_trials"] = max(0, int(getattr(response, "clinical_trials_coins", 0)))
                coins["knowledge_base"] = max(0, int(getattr(response, "knowledge_base_coins", 0)))
                coins["literature"] = max(0, int(getattr(response, "literature_coins", dynamic_coins)))
                reasoning = str(getattr(response, "reasoning", reasoning))
        except Exception as exc:
            log.warning(f"Failed to parse source_selector coins: {exc}")

        base_coins = config.get("retrieval.base_coins_per_source", 1)
        coins["clinical_trials"] += base_coins
        coins["knowledge_base"] += base_coins
        coins["literature"] += base_coins

        log.info(f"source_selector allocated coins {coins} (LLM reasoning: {reasoning})")
        return {
            "retrieval_source": coins,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_source_coins": coins,
                        "reasoning": reasoning,
                        "subclaim_id": subclaim_id,
                    }),
                    name="source_selector",
                )
            ],
        }

    @log_node("retrieval")
    def downloader_agent_node(state: State):
        log.info("downloader_agent start")
        query = state.get("subclaim") or _message_text(state["messages"][0])
        subclaim_id = state.get("subclaim_id")
        allocated_coins = state.get("retrieval_source") or {"literature": config.get("retrieval.dynamic_coins", 3) + config.get("retrieval.base_coins_per_source", 1)}
        
        all_downloaded_chunks = []
        all_search_queries = []
        queries_by_source = {}
        reasonings = []

        def process_source(source, num_coins):
            if num_coins <= 0:
                return [], [], ""
            
            sys_msg = SystemMessage(content=retrieval_query_generation_prompt.format(
                num_queries=num_coins, target_source=source
            ))
            messages = [sys_msg, HumanMessage(content=query)]
            
            query_generator_llm = base_llm.with_structured_output(
                get_retrieval_query_generation_schema(num_coins), method="function_calling"
            )
            response = query_generator_llm.invoke(messages)
            generated_queries = []
            rsn = ""
            if isinstance(response, dict):
                generated_queries = response.get("search_queries") or []
                rsn = str(response.get("reasoning", ""))
            else:
                generated_queries = getattr(response, "search_queries", []) or []
                rsn = str(getattr(response, "reasoning", ""))
                
            search_queries = _normalize_search_queries(generated_queries, query)
            search_queries = search_queries[:num_coins]
            
            log.info(f"downloader_agent downloading from {source} with args: {search_queries}")
            docs = download_documents.invoke(
                {"sub_id": subclaim_id, "search_queries": search_queries, "target_source": source}
            )
            return search_queries, docs, rsn

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_source = {
                executor.submit(process_source, src, coins_amt): src 
                for src, coins_amt in allocated_coins.items() if coins_amt > 0
            }
            
            for future in concurrent.futures.as_completed(future_to_source):
                src = future_to_source[future]
                try:
                    sq, docs, rsn = future.result()
                    all_search_queries.extend(sq)
                    queries_by_source[src] = sq
                    all_downloaded_chunks.extend(docs)
                    if rsn:
                        reasonings.append(f"{src}: {rsn}")
                except Exception as exc:
                    log.error(f"downloader_agent error for {src}: {exc}")

        combined_reasoning = " | ".join(reasonings) or "fallback to input query"
        primary_query = all_search_queries[0] if all_search_queries else query

        return {
            "retrieval_source": allocated_coins,
            "retrieval_query": primary_query,
            "all_search_queries": all_search_queries,
            "queries_by_source": queries_by_source,
            "downloaded_chunks": all_downloaded_chunks,
            "messages": [
                HumanMessage(
                    content=str({
                        "retrieval_source_coins": allocated_coins,
                        "queries_by_source": queries_by_source,
                        "subclaim_id": subclaim_id,
                        "reasoning": combined_reasoning,
                        "downloaded_chunks_count": len(all_downloaded_chunks),
                    }),
                    name="downloader_agent",
                )
            ],
        }

    @log_node("retrieval")
    def hybrid_retriever_node(state: State):
        log.info("hybrid_retriever start")
        # We MUST use the full subclaim for semantic (dense) retrieval, not the short keyword queries.
        subclaim = state.get("subclaim") or _message_text(state["messages"][0])
        all_search_queries = state.get("all_search_queries") or []
            
        chunks = state.get("downloaded_chunks") or []
        chunks_json = json.dumps(chunks)
        
        top_k = config.get("retrieval.hybrid.top_k", 5)
        alpha = float(config.get("retrieval.hybrid.alpha", 0.5))
        log.info(f"hybrid_retriever using alpha={alpha} for subclaim: {subclaim}")
        
        chunk_scores: dict[str, float] = {}
        chunk_data: dict[str, dict] = {}
        
        # We only need to run the retrievers once using the full subclaim
        if alpha > 0.0:
            try:
                dense_results = dense_retrieve_tool.invoke({"query": subclaim, "chunks": chunks_json, "top_k": top_k})
                for rank, chunk in enumerate(dense_results, 1):
                    cid = str(chunk.get("metadata", {}).get("id", "")) + "_" + chunk.get("text", "")[:20]
                    if cid not in chunk_data:
                        chunk_data[cid] = chunk
                    score_increment = alpha * (1.0 / (60.0 + rank))
                    chunk_scores[cid] = chunk_scores.get(cid, 0.0) + score_increment
            except Exception as exc:
                log.error(f"Dense retrieve failed for subclaim '{subclaim}': {exc}")
                
        if alpha < 1.0:
            # For sparse (BM25), keyword queries are much better than the verbose subclaim,
            # especially since our BM25 doesn't filter stopwords.
            sparse_query = " ".join(all_search_queries) if all_search_queries else subclaim
            try:
                sparse_results = sparse_retrieve_tool.invoke({"query": sparse_query, "chunks": chunks_json, "top_k": top_k})
                for rank, chunk in enumerate(sparse_results, 1):
                    cid = str(chunk.get("metadata", {}).get("id", "")) + "_" + chunk.get("text", "")[:20]
                    if cid not in chunk_data:
                        chunk_data[cid] = chunk
                    score_increment = (1.0 - alpha) * (1.0 / (60.0 + rank))
                    chunk_scores[cid] = chunk_scores.get(cid, 0.0) + score_increment
            except Exception as exc:
                log.error(f"Sparse retrieve failed for sparse_query '{sparse_query}': {exc}")

        sorted_cids = sorted(chunk_scores.keys(), key=lambda c: chunk_scores[c], reverse=True)
        final_chunks = [chunk_data[cid] for cid in sorted_cids[:top_k]]
        
        log.info(f"hybrid_retriever extracted {len(final_chunks)} total unique chunks via RRF.")
        return {
            "retrieved_chunks": final_chunks,
            "messages": [
                HumanMessage(
                    content=str({
                        "hybrid_alpha": alpha,
                        "retrieved_chunks_count": len(final_chunks),
                    }),
                    name="hybrid_retriever",
                )
            ],
        }

    builder = StateGraph(State)
    builder.add_node("source_selector", source_selector_node)
    builder.add_node("downloader_agent", downloader_agent_node)
    builder.add_node("hybrid_retriever", hybrid_retriever_node)

    builder.add_edge(START, "source_selector")
    builder.add_edge("source_selector", "downloader_agent")
    builder.add_edge("downloader_agent", "hybrid_retriever")
    builder.add_edge("hybrid_retriever", END)

    return builder.compile()
