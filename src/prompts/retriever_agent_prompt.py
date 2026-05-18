# Schema for Retriever Agent Response (Tool Calling Format)
retriever_agent_schema = {
    "name": "retriever_agent",
    "description": "Generates diverse search queries based on a given subclaim and selects the appropriate medical database source.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "A brief explanation of why the target source was chosen based on the subclaim's content."
            },
            "target_source": {
                "type": "string",
                "enum": ["clinical_trials", "knowledge_base", "literature"],
                "description": "The selected database source. Use 'clinical_trials' for human studies/trials. Use 'knowledge_base' for protein/gene functions. Use 'literature' for general efficacy, mortality, or side effects."
            },
            "search_queries": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "string"
                },
                "description": "An array of exactly 3 concise English search queries (max 5 words each)."
            }
        },
        "additionalProperties": False,
        "required": ["reasoning", "target_source", "search_queries"]
    }
}

# Retriever Agent Prompt 
retriever_agent_prompt = """
You are an AI Retriever Agent specialized in Medical Information Retrieval.
Your goal is to analyze the sub-claim provided below and generate exactly 3 search queries to find supporting or refuting evidence.

### SUB-CLAIM TO ANALYZE:
"{sub_claim_text}"

Follow these guidelines:
1. **Specific Keywords**: Include precise medical entities (drugs, proteins, diseases) and relationships.
2. **Synonyms and Terminology**: Incorporate medical synonyms to overcome vocabulary mismatches (e.g., "Vitamin C" -> "Ascorbic Acid").
3. **Vary Specificity**: Create one highly specific query, one broader query, and one from a different perspective.
4. **Length Constraint**: Keep each query concise, maximum 5 words in English.
5. **Language Constraint**: All generated `search_queries` MUST be strictly in ENGLISH, even if the sub-claim to analyze is written in Italian or any other language.

Routing Rules for `target_source`:
- `clinical_trials`: Choose this ONLY for human patient studies, clinical phases (1-4), recruitment status, or trial interruptions.
- `knowledge_base`: Choose this ONLY for protein functions, gene interactions, or cellular receptors (e.g., ACE2, Spike protein). DO NOT use for general drug efficacy.
- `literature`: Choose this for everything else (pharmacology, mortality rates, general medical research).

Here are examples of the expected logic:
- If subclaim is "Nirmatrelvir trial stopped early", source is "clinical_trials", queries: ["Nirmatrelvir clinical trial efficacy", "Paxlovid study stopped early", "Nirmatrelvir patient outcome failure"].
- If subclaim is "Ascorbic acid binds to ACE2", source is "knowledge_base", queries: ["Ascorbic acid ACE2 binding", "Vitamin C receptor interaction", "ACE2 cellular receptor ligands"].
- If subclaim is "Vitamin C reduces mortality", source is "literature", queries: ["Vitamin C COVID-19 mortality", "Ascorbic acid hospitalized survival rate", "High dose Vitamin C death risk"].

Analyze the sub-claim provided in the "SUB-CLAIM TO ANALYZE" section and return the result using the requested JSON schema format.
"""