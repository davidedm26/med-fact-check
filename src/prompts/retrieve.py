retrieval_source_selection_prompt = """
You are the source-selection step in a medical fact-checking pipeline.

Your goal is to inspect a sub-claim and distribute a budget of {total_coins} "coins" across the available evidence sources based on where you expect to find the best evidence.
You can put all {total_coins} coins on a single source, or distribute them across multiple sources.
The sum of all allocated coins must be exactly {total_coins}.
CRITICAL: You must allocate strictly INTEGER values for coins (e.g., 0, 1, 2). Fractions or decimals are NOT allowed.

The sub-claim will be provided in the HumanMessage.

Available sources:
- `systematic_reviews`: high-level evidence from systematic reviews and meta-analyses. Use when the sub-claim involves treatment comparisons, aggregated outcomes, or established clinical consensus.
- `knowledge_base`: proteins, genes, receptors, binding, expression, or molecular pathways. DO NOT use this for complex in-vivo experiments, animal models (e.g., knockin mice), or specific research findings. Use ONLY for basic molecular/genetic definitions.
- `literature`: broad medical research, general drug efficacy, mortality, side effects, epidemiological stats, animal models, and specific laboratory experiments.

Examples for a budget of 3 coins:
1. "Varenicline monotherapy is more effective than combination nicotine replacement therapies." -> systematic_reviews: 3, knowledge_base: 0, literature: 0 (comparing therapies with aggregated evidence)
2. "Glycyl-tRNA synthetase gene involved in development of Charcot-Marie-Tooth disease." -> systematic_reviews: 0, knowledge_base: 3, literature: 0 (genes and pathways)
3. "Metformin interferes thyroxine absorption." -> systematic_reviews: 1, knowledge_base: 0, literature: 2 (general drug interaction, some meta-analytic evidence available)

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
            "systematic_reviews_coins": {
                "type": "integer",
                "description": "Coins allocated to systematic_reviews"
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
        "required": ["reasoning", "systematic_reviews_coins", "knowledge_base_coins", "literature_coins"]
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
6. CRITICAL: NEVER drop the primary subject, disease, or core entity from the original claim (e.g. if the claim is about 'COVID-19', 'Alzheimer', or 'Metformin', that exact entity MUST be present in every generated query).

Tailor the queries to the selected source:
- `systematic_reviews`: extract ONLY 2-3 core medical keywords (e.g. disease and drug). CRITICAL: DO NOT add meta-words like "treatment", "comparison", "risk", "outcomes", or "systematic review" because the search engine automatically applies these filters.
- `knowledge_base`: extract ONLY 1-2 core keywords (the exact protein, gene, or pathway name). CRITICAL: DO NOT add meta-words like "pathway", "expression", "protein", or "binding".
- `literature`: emphasize drug/treatment claims, efficacy, mortality, side effects, infection risk, prognosis, and general medical research (max 4-5 words).

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
