retrieval_source_selection_prompt = """
You are the source-selection step in a medical fact-checking pipeline.

Your goal is to inspect a sub-claim and distribute a budget of {total_coins} "coins" across the available evidence sources based on where you expect to find the best evidence.
You can put all {total_coins} coins on a single source, or distribute them across multiple sources.
The sum of all allocated coins must be exactly {total_coins}.

The sub-claim will be provided in the HumanMessage.

Available sources:
- `clinical_trials`: human patient studies, clinical phases (1-4), recruitment status, or trial comparisons. Use when the sub-claim compares therapies or mentions patient trials.
- `knowledge_base`: proteins, genes, receptors, binding, expression, or molecular pathways. Use when the sub-claim focuses on molecular biology or genetics.
- `literature`: broad medical research, general drug efficacy, mortality, side effects, or epidemiological stats.

Examples for a budget of 3 coins:
1. "Varenicline monotherapy is more effective than combination nicotine replacement therapies." -> clinical_trials: 3, knowledge_base: 0, literature: 0 (comparing therapies)
2. "Glycyl-tRNA synthetase gene involved in development of Charcot-Marie-Tooth disease." -> clinical_trials: 0, knowledge_base: 3, literature: 0 (genes and pathways)
3. "Metformin interferes thyroxine absorption." -> clinical_trials: 0, knowledge_base: 1, literature: 2 (general drug interaction but might involve molecular pathways)

Do not invent evidence.
"""

retrieval_source_selection_schema = {
    "name": "retrieval_source_selection",
    "description": "Distributes a budget of coins among the available database sources based on relevance.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation for the coin allocation.",
                "maxLength": 100 # Limit reasoning to 100 characters for conciseness
            },
            "clinical_trials_coins": {
                "type": "integer",
                "description": "Coins allocated to clinical_trials"
            },
            "knowledge_base_coins": {
                "type": "integer",
                "description": "Coins allocated to knowledge_base"
            },
            "literature_coins": {
                "type": "integer",
                "description": "Coins allocated to literature"
            }
        },
        "additionalProperties": False,
        "required": ["reasoning", "clinical_trials_coins", "knowledge_base_coins", "literature_coins"]
    }
}

retrieval_query_generation_prompt = """
You are the query-generation step in a medical fact-checking pipeline.

Your goal is to generate exactly {num_queries} concise search queries for a sub-claim, tailored for the selected source below.

Selected source: {target_source}

The sub-claim will be provided in the HumanMessage.

Follow these guidelines:
1. Include precise medical entities and relationships.
2. Use medical synonyms to overcome vocabulary mismatches.
3. Create diverse queries (e.g. one specific, one broader) based on the number of requested queries.
4. Keep each query concise, maximum 5 words in English.
5. All generated `search_queries` MUST be strictly in ENGLISH, even if the sub-claim is written in Italian or any other language.

Tailor the queries to the selected source:
- `clinical_trials`: emphasize trial identifiers, phases, recruitment, enrollment, or interruption.
- `knowledge_base`: emphasize proteins, genes, receptors, binding, expression, or pathways.
- `literature`: emphasize drug/treatment claims, efficacy, mortality, side effects, infection risk, prognosis, and general medical research.

Do not invent evidence.
"""

def get_retrieval_query_generation_schema(num_queries: int) -> dict:
    return {
        "name": "retrieval_query_generation",
        "description": "Generates concise search queries for a selected medical database source.",
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
                    "items": {
                        "type": "string"
                    },
                    "description": f"The exact number of English search queries requested ({num_queries}).",
                    "minItems": num_queries,
                    "maxItems": num_queries
                }
            },
            "additionalProperties": False,
            "required": ["reasoning", "search_queries"]
        }
    }
