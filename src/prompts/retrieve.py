retrieval_source_selection_prompt = """
You are the source-selection step in a medical fact-checking pipeline.

Your goal is to inspect a sub-claim and choose the best evidence source.

The sub-claim will be provided in the HumanMessage.

Choose exactly one source per sub-claim.

Available sources:
- `clinical_trials`: human patient studies, clinical phases (1-4), recruitment status, or trial comparisons. Use when the sub-claim compares therapies or mentions patient trials.
- `knowledge_base`: proteins, genes, receptors, binding, expression, or molecular pathways. Use when the sub-claim focuses on molecular biology or genetics.
- `literature`: broad medical research, general drug efficacy, mortality, side effects, or epidemiological stats.

Examples:
1. "Varenicline monotherapy is more effective than combination nicotine replacement therapies." -> clinical_trials (comparing therapies)
2. "Glycyl-tRNA synthetase gene involved in development of Charcot-Marie-Tooth disease." -> knowledge_base (genes and pathways)
3. "Metformin interferes thyroxine absorption." -> literature (general drug interaction)

Do not invent evidence.
"""

retrieval_source_selection_schema = {
    "name": "retrieval_source_selection",
    "description": "Selects the best medical database source for a subclaim.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation for the chosen source.",
                "maxLength": 100 # Limit reasoning to 100 characters for conciseness
            },
            "target_source": {
                "type": "string",
                "enum": ["clinical_trials", "knowledge_base", "literature"],
                "description": "The selected database source."
            }
        },
        "additionalProperties": False,
        "required": ["reasoning", "target_source"]
    }
}

retrieval_query_generation_prompt = """
You are the query-generation step in a medical fact-checking pipeline.

Your goal is to generate exactly 3 concise search queries for a sub-claim, using the selected source below.

Selected source: {target_source}

The sub-claim will be provided in the HumanMessage.

Follow these guidelines:
1. Include precise medical entities and relationships.
2. Use medical synonyms to overcome vocabulary mismatches.
3. Create one highly specific query, one broader query, and one from a different perspective.
4. Keep each query concise, maximum 5 words in English.
5. All generated `search_queries` MUST be strictly in ENGLISH, even if the sub-claim is written in Italian or any other language.

Tailor the queries to the selected source:
- `clinical_trials`: emphasize trial identifiers, phases, recruitment, enrollment, or interruption.
- `knowledge_base`: emphasize proteins, genes, receptors, binding, expression, or pathways.
- `literature`: emphasize drug/treatment claims, efficacy, mortality, side effects, infection risk, prognosis, and general medical research.

Do not invent evidence.
"""

retrieval_query_generation_schema = {
    "name": "retrieval_query_generation",
    "description": "Generates three search queries for a selected medical database source.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation for the generated queries."
            },
            "search_queries": {
                "type": "array",
                "minItems": 3, # TO DO: This number should be configurable
                "maxItems": 3,
                "items": {
                    "type": "string"
                },
                "description": "Exactly 3 concise English search queries."
            }
        },
        "additionalProperties": False,
        "required": ["reasoning", "search_queries"]
    }
}

retrieval_strategy_router_prompt = """
You are a routing agent for medical evidence retrieval.

Choose the retrieval strategy that best fits the query:
- `sparse`: use when the query is a highly specific granular search relying on exact acronyms, literal dates, identifiers, or isolated entities (e.g., "32% liver transplantation methadone 2001").
- `dense`: use when the query represents complex phrases, sentences, comparisons, or broader medical concepts where semantic matching is better than exact keyword matching.

Examples:
1. "Varenicline vs bupropion combination therapy efficacy" -> dense (complex comparison)
2. "liver transplantation methadone discontinuation 2001" -> sparse (highly granular literal search)
3. "Metformin thyroxine absorption interaction" -> dense (semantic interaction)
4. "GARS gene mutations CMT" -> sparse (specific acronyms)

Default to `dense` when uncertain.
Do not invent evidence.
"""

retrieval_strategy_router_schema = {
    "name": "retrieval_strategy_router",
    "description": "Chooses the retrieval strategy for a query.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "retrieval_strategy": {
                "type": "string",
                "enum": ["sparse", "dense"],
                "description": "The selected retrieval strategy."
            },
            "reasoning": {
                "type": "string",
                "description": "Short explanation for the selected strategy."
            }
        },
        "additionalProperties": False,
        "required": ["retrieval_strategy", "reasoning"]
    }
}