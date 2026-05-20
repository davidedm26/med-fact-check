from typing import Annotated, Dict, List, Optional
import operator
from langgraph.graph import MessagesState

# Helper function to extract text from a message, which can be a string, a tuple/list, or an object with a 'content' attribute.
def _message_text(message): 
    if hasattr(message, "content"): 
        return message.content 
    if isinstance(message, (tuple, list)) and len(message) > 1: # this case is for when the message is a tuple or list, and we want to extract the second element as the text. 
        return message[1]
    return str(message)
 
# State class that extends MessagesState and includes additional fields for managing the state of a conversation or process.
class State(MessagesState):
    next: str # The next step or action to be taken in the process.
    predicates: Optional[List[Dict[str, str]]] # A list of predicates, which are conditions or statements that can be evaluated.
    predicate_type_dict: Optional[List[Dict[str, str]]] # A dictionary mapping predicate types to their corresponding verifiable/non-verifiable categories.
    verifiable_subclaims: Optional[List[Dict[str, str]]] # A list of filtered predicate objects that survived classification.
    subclaim_results: Annotated[List[Dict[str, object]], operator.add]
    retrieval_query: Optional[str]
    retrieval_source: Optional[str]
    retrieval_strategy: Optional[str]
    subclaim_id: Optional[str]
    downloaded_documents: Optional[List[Dict[str, object]]]
    sparse_top_k_chunks: Optional[List[Dict[str, object]]]
    dense_top_k_chunks: Optional[List[Dict[str, object]]]
