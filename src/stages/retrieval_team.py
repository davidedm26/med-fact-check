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
from tools.retrieve.reranker import get_default_reranker
from utils.logger import get_logger
from utils.mongo_logger import log_node
from utils.config import config

log = get_logger("RetrievalTeam")

def get_retrieval_nodes(source_selector_llm, base_llm):
    """Get the individual retrieval node functions."""

    RETRIEVAL_STRATEGY_TO_NODE = {
        "sparse": "sparse_retriever",
        "dense": "dense_retriever",
    }

    VALID_TARGET_SOURCES = {"systematic_reviews", "knowledge_base", "literature"}

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
        coins = {"systematic_reviews": 0, "knowledge_base": 0, "literature": dynamic_coins}
        reasoning = "fallback to literature"
        
        try:
            if isinstance(response, dict):
                coins["systematic_reviews"] = max(0, int(response.get("systematic_reviews_coins", 0)))
                coins["knowledge_base"] = max(0, int(response.get("knowledge_base_coins", 0)))
                coins["literature"] = max(0, int(response.get("literature_coins", dynamic_coins)))
                reasoning = str(response.get("reasoning", reasoning))
            else:
                coins["systematic_reviews"] = max(0, int(getattr(response, "systematic_reviews_coins", 0)))
                coins["knowledge_base"] = max(0, int(getattr(response, "knowledge_base_coins", 0)))
                coins["literature"] = max(0, int(getattr(response, "literature_coins", dynamic_coins)))
                reasoning = str(getattr(response, "reasoning", reasoning))
        except Exception as exc:
            log.warning(f"Failed to parse source_selector coins: {exc}")

        base_coins = config.get("retrieval.base_coins_per_source", 1)
        coins["systematic_reviews"] += base_coins
        coins["knowledge_base"] += base_coins
        coins["literature"] += base_coins

        log.info(f"source_selector allocated coins {coins} (LLM reasoning: {reasoning})")
        return {
            "subclaim_id": subclaim_id,
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
        queries_by_source = {}
        download_stats = {}
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
            result = download_documents.invoke(
                {"sub_id": subclaim_id, "search_queries": search_queries, "target_source": source}
            )
            return search_queries, result["chunks"], rsn, result.get("stats", {})

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_source = {
                executor.submit(process_source, src, coins_amt): src 
                for src, coins_amt in allocated_coins.items() if coins_amt > 0
            }
            
            for future in concurrent.futures.as_completed(future_to_source):
                src = future_to_source[future]
                try:
                    sq, docs, rsn, stats = future.result()
                    queries_by_source[src] = sq
                    all_downloaded_chunks.extend(docs)
                    download_stats[src] = stats
                    if rsn:
                        reasonings.append(f"{src}: {rsn}")
                except Exception as exc:
                    log.error(f"downloader_agent error for {src}: {exc}")

        # Fallback to literature if too few chunks were retrieved
        min_chunks = config.get("retrieval.min_chunks_per_subclaim", 5)
        if len(all_downloaded_chunks) < min_chunks:
            fallback_coins = config.get("retrieval.dynamic_coins", 3)
            log.warning(f"Only {len(all_downloaded_chunks)} chunks retrieved. Falling back to literature with {fallback_coins} coins.")
            try:
                sq, docs, rsn, stats = process_source("literature", fallback_coins)
                if "literature" in queries_by_source:
                    queries_by_source["literature"].extend(sq)
                else:
                    queries_by_source["literature"] = sq
                
                all_downloaded_chunks.extend(docs)
                
                if "literature" in download_stats:
                    for k, v in stats.items():
                        if isinstance(v, int):
                            download_stats["literature"][k] = download_stats["literature"].get(k, 0) + v
                else:
                    download_stats["literature"] = stats
                    
                if rsn:
                    reasonings.append(f"literature (fallback): {rsn}")
            except Exception as exc:
                log.error(f"Fallback to literature failed: {exc}")

        import random
        max_chunks = config.get("retrieval.max_chunks_per_subclaim", 150)
        if len(all_downloaded_chunks) > max_chunks:
            log.warning(f"Extracted {len(all_downloaded_chunks)} chunks, exceeding the limit of {max_chunks}. Programmatically sampling {max_chunks} chunks.")
            all_downloaded_chunks = random.sample(all_downloaded_chunks, max_chunks)

        combined_reasoning = " | ".join(reasonings) or "fallback to input query"

        return {
            "subclaim_id": subclaim_id,
            "retrieval_source": allocated_coins,
            "queries_by_source": queries_by_source,
            "download_stats": download_stats,
            "downloaded_chunks": all_downloaded_chunks,
            "downloaded_chunks_count": len(all_downloaded_chunks),
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
        subclaim_id = state.get("subclaim_id")
        queries_by_source = state.get("queries_by_source") or {}
        
        # Flatten the dictionary to get all keyword queries for sparse retrieval
        all_search_queries = [q for queries in queries_by_source.values() for q in queries]
            
        chunks = state.get("downloaded_chunks") or []
        chunks_json = json.dumps(chunks)
        
        dense_top_k = config.get("retrieval.hybrid.dense_top_k", 10)
        sparse_top_k = config.get("retrieval.hybrid.sparse_top_k", 10)
        log.info(f"hybrid_retriever using dense_top_k={dense_top_k}, sparse_top_k={sparse_top_k} for subclaim: {subclaim}")
        
        chunk_data: dict[str, dict] = {}
        
        if dense_top_k > 0:
            try:
                dense_results = dense_retrieve_tool.invoke({"query": subclaim, "chunks": chunks_json, "top_k": dense_top_k})
                for chunk in dense_results:
                    cid = str(chunk.get("metadata", {}).get("id", "")) + "_" + chunk.get("text", "")[:20]
                    if cid not in chunk_data:
                        chunk_data[cid] = chunk
            except Exception as exc:
                log.error(f"Dense retrieve failed for subclaim '{subclaim}': {exc}")
                
        if sparse_top_k > 0:
            # For sparse (BM25), keyword queries are much better than the verbose subclaim,
            # especially since our BM25 doesn't filter stopwords.
            sparse_query = " ".join(all_search_queries) if all_search_queries else subclaim
            try:
                sparse_results = sparse_retrieve_tool.invoke({"query": sparse_query, "chunks": chunks_json, "top_k": sparse_top_k})
                for chunk in sparse_results:
                    cid = str(chunk.get("metadata", {}).get("id", "")) + "_" + chunk.get("text", "")[:20]
                    if cid not in chunk_data:
                        chunk_data[cid] = chunk
            except Exception as exc:
                log.error(f"Sparse retrieve failed for sparse_query '{sparse_query}': {exc}")

        union_chunks = list(chunk_data.values())
        log.info(f"hybrid_retriever extracted {len(union_chunks)} unique candidate chunks.")

        rerank_top_k = config.get("retrieval.hybrid.rerank_top_k", 5)
        
        # Rerank all candidate chunks
        if union_chunks:
            log.info(f"Reranking {len(union_chunks)} chunks using Cross-Encoder...")
            reranker = get_default_reranker()
            reranked_chunks = reranker.rerank(query=subclaim, chunks=union_chunks, top_k=len(union_chunks))
        else:
            reranked_chunks = []

        # Diversity constraint: limit chunks per document to avoid a single paper dominating the results
        max_per_doc = config.get("retrieval.hybrid.max_chunks_per_doc", 2)
        doc_counts: dict[str, int] = {}
        final_chunks = []
        
        for chunk in reranked_chunks:
            if len(final_chunks) >= rerank_top_k:
                break
            doc_id = str(chunk.get("metadata", {}).get("id", ""))
            current_count = doc_counts.get(doc_id, 0)
            if current_count < max_per_doc:
                final_chunks.append(chunk)
                doc_counts[doc_id] = current_count + 1

        log.info(f"hybrid_retriever selected {len(final_chunks)} final chunks after reranking and diversity constraint (max {max_per_doc}/doc).")
        
        return {
            "subclaim_id": subclaim_id,
            "retrieved_chunks": final_chunks,
            "retrieved_chunks_count": len(final_chunks),
            "messages": [
                HumanMessage(
                    content=str({
                        "dense_top_k": dense_top_k,
                        "sparse_top_k": sparse_top_k,
                        "retrieved_chunks_count": len(final_chunks),
                    }),
                    name="hybrid_retriever",
                )
            ],
        }

    return {
        "source_selector": source_selector_node,
        "downloader_agent": downloader_agent_node,
        "hybrid_retriever": hybrid_retriever_node,
    }

def build_retrieval_graph(source_selector_llm, base_llm):
    """Build the unified retrieval subgraph."""
    nodes = get_retrieval_nodes(source_selector_llm, base_llm)
    builder = StateGraph(State)
    builder.add_node("source_selector", nodes["source_selector"])
    builder.add_node("downloader_agent", nodes["downloader_agent"])
    builder.add_node("hybrid_retriever", nodes["hybrid_retriever"])

    builder.add_edge(START, "source_selector")
    builder.add_edge("source_selector", "downloader_agent")
    builder.add_edge("downloader_agent", "hybrid_retriever")
    builder.add_edge("hybrid_retriever", END)

    return builder.compile()
