from typing import Annotated, Dict, List, Optional
import operator
from langgraph.graph import MessagesState

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
