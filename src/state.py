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
 
def take_last(left, right):
    return right if right is not None else left

# State class that extends MessagesState and includes additional fields for managing the state of a conversation or process.
class State(MessagesState):
    run_id: Annotated[Optional[str], take_last]  # UUID identifying the pipeline run (for MongoDB logging)
    next: Annotated[str, take_last] # The next step or action to be taken in the process.
    predicates: Annotated[Optional[List[Dict[str, str]]], take_last] # A list of predicates, which are conditions or statements that can be evaluated.
    predicate_type_dict: Annotated[Optional[List[Dict[str, str]]], take_last] # A dictionary mapping predicate types to their corresponding verifiable/non-verifiable categories.
    verifiable_subclaims: Annotated[Optional[List[Dict[str, str]]], take_last] # A list of filtered predicate objects that survived classification.
    subclaim_results: Annotated[List[Dict[str, object]], operator.add]
    retrieval_source: Annotated[Optional[Dict[str, int]], take_last]
    queries_by_source: Annotated[Optional[Dict[str, List[str]]], take_last]
    download_stats: Annotated[Optional[Dict[str, dict]], take_last]
    subclaim_id: Annotated[Optional[str], take_last]
    subclaim: Annotated[Optional[str], take_last]
    downloaded_chunks: Annotated[Optional[List[Dict[str, object]]], take_last]
    retrieved_chunks: Annotated[Optional[List[Dict[str, object]]], take_last]
    # ── Evaluation Team fields ──
    evaluation_results: Annotated[List[Dict[str, object]], operator.add]  # Aggregated evaluation results (label + confidence + justification) for each subclaim
    subclaim_justification: Annotated[Optional[str], take_last]  # Output of the Reasoning Agent (used internally by the evaluation subgraph)
    supporting_quotes: Annotated[Optional[List[str]], take_last]  # Key supporting evidence excerpts selected by the Reasoning Agent
    refuting_quotes: Annotated[Optional[List[str]], take_last]  # Key refuting evidence excerpts selected by the Reasoning Agent
    reasoning_conclusion: Annotated[Optional[str], take_last]  # Preliminary conclusion from the Reasoning Agent
    evidence_text: Annotated[Optional[str], take_last]  # Formatted evidence chunks text (input to the Reasoning Agent)
    distilled_evidence: Annotated[Optional[str], take_last]  # Purified facts extracted by the Reasoning Agent
    evidence_verdict_hint: Annotated[Optional[str], take_last]  # One-sentence summary of what the evidence says about the claim
    final_verdict: Annotated[Optional[Dict[str, object]], take_last]  # Aggregated final verdict for the whole claim (label, confidence, breakdown)
