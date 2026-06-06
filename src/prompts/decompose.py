# Claim decomposition response schema
claim_decomposition = { 
    "name": "claim_decomposition",
    "description": "Splits an input claim into multiple subclaims.", # Description is passed to the LLM to help it understand the purpose of the function
    "strict": True, # Enforce that the output strictly adheres to the defined schema, with no extra fields or missing required fields
    "parameters": { # Define the structure of the expected output from the LLM
        "type": "object", # The output should be a JSON object
        "properties": {
            "thought_process": {
                "type": "string",
                "description": "Analyze the claim step by step, identify conditions, and plan the decomposition before generating the predicates."
            },
            "predicates": { 
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "relation": {
                            "type": "string",
                            "description": "The predicate or relation extracted from the claim."
                        },
                        "subject": {
                            "type": "string",
                            "description": "The subject participating in the relation."
                        },
                        "object": {
                            "type": "string",
                            "description": "The object or target of the relation."
                        },
                        "search_query": {
                            "type": "string",
                            "description": "A concise declarative statement to verify the predicate."
                        }
                    },
                    "additionalProperties": False, # Ensure no extra fields are included in each predicate object
                    "required": ["relation", "subject", "object", "search_query"]
                },
                "description": "The structured predicates derived from the input claim."
            }
        },
        "additionalProperties": False, # Ensure no extra fields are included in the main object
        "required": ["thought_process", "predicates"]
    }
}



# Claim decomposition examples
claim_decomposition_examples = [
    {
        "input_claim": "ciao / hello there! wtf",
        "thought_process": "The input is conversational fragments and slang. No verifiable medical facts are present.",
        "predicates": []
    },
    {
        "input_claim": "They're pushing this new injection that's supposed to clear it up in weeks, but everyone online says it just makes the redness worse and your wallet lighter.",
        "thought_process": "The input contains an assertion about a new injection's intended effect and an anecdotal rumor. I will extract both as declarative statements, preserving the attribution for the rumor.",
        "predicates": [
            {
                "relation": "Supposed to clear",
                "subject": "The new injection",
                "object": "it up in weeks",
                "search_query": "The new injection is supposed to clear it up in weeks."
            },
            {
                "relation": "Says",
                "subject": "Everyone online",
                "object": "the new injection just makes the redness worse and your wallet lighter",
                "search_query": "Everyone online says the new injection just makes the redness worse and your wallet lighter."
            }
        ]
    },
    {
        "input_claim": "Does the Mediterranean diet improve cardiovascular health? Can it reduce the risk of heart attacks?",
        "thought_process": "The input contains questions ('Does the Mediterranean diet improve...', 'Can it reduce...'). According to the rules, I MUST convert questions into positive, declarative statements. The statements will be: 'The Mediterranean diet improves cardiovascular health' and 'The Mediterranean diet reduces the risk of heart attacks'. Now I will extract the predicates from these statements.",
        "predicates": [
            {
                "relation": "Improve",
                "subject": "The Mediterranean diet",
                "object": "cardiovascular health",
                "search_query": "The Mediterranean diet improves cardiovascular health."
            },
            {
                "relation": "ReduceRisk",
                "subject": "The Mediterranean diet",
                "object": "heart attacks",
                "search_query": "The Mediterranean diet reduces the risk of heart attacks."
            }
        ]
    },
    {
        "input_claim": "Metformin is recommended as a first-line pharmacological treatment for type 2 diabetes mellitus, unless the patient has severe renal impairment (eGFR < 30 mL/min) or a history of lactic acidosis, in which case DPP-4 inhibitors should be considered instead.",
        "thought_process": "The input contains conditional recommendations ('unless...'). I need to distribute these conditions. Metformin is recommended IF NO severe renal impairment AND IF NO history of lactic acidosis. DPP-4 inhibitors are recommended IF severe renal impairment OR IF history of lactic acidosis.",
        "predicates": [
            {
                "relation": "Recommended",
                "subject": "Metformin",
                "object": "type 2 diabetes mellitus",
                "search_query": "Metformin is recommended as a first-line pharmacological treatment for type 2 diabetes mellitus in patients without severe renal impairment (eGFR < 30 mL/min)."
            },
            {
                "relation": "Recommended",
                "subject": "Metformin",
                "object": "type 2 diabetes mellitus",
                "search_query": "Metformin is recommended as a first-line pharmacological treatment for type 2 diabetes mellitus in patients without a history of lactic acidosis."
            },
            {
                "relation": "Recommended",
                "subject": "DPP-4 inhibitors",
                "object": "type 2 diabetes mellitus",
                "search_query": "DPP-4 inhibitors should be considered as a treatment for type 2 diabetes mellitus if the patient has severe renal impairment (eGFR < 30 mL/min)."
            },
            {
                "relation": "Recommended",
                "subject": "DPP-4 inhibitors",
                "object": "type 2 diabetes mellitus",
                "search_query": "DPP-4 inhibitors should be considered as a treatment for type 2 diabetes mellitus if the patient has a history of lactic acidosis."
            }
        ]
    },
    {
        "input_claim": "The daily use of sedatives and sleeping pills such as benzodiazepines increases the risk of Alzheimer's disease, but it has no effect on vascular dementia.",
        "thought_process": "The input contains a compound subject ('sedatives' and 'sleeping pills such as benzodiazepines') and multiple distinct factual assertions ('increases the risk of Alzheimer's disease', 'has no effect on vascular dementia'). I must keep each predicate minimal and split conjunctions.",
        "predicates": [
            {
                "relation": "IncreaseRisk",
                "subject": "Sedatives",
                "object": "Alzheimer's disease",
                "search_query": "Sedatives increase the risk of Alzheimer's disease."
            },
            {
                "relation": "IncreaseRisk",
                "subject": "Sleeping pills such as benzodiazepines",
                "object": "Alzheimer's disease",
                "search_query": "Sleeping pills such as benzodiazepines increase the risk of Alzheimer's disease."
            },
            {
                "relation": "HasNoEffect",
                "subject": "Sedatives",
                "object": "vascular dementia",
                "search_query": "Sedatives have no effect on vascular dementia."
            },
            {
                "relation": "HasNoEffect",
                "subject": "Sleeping pills such as benzodiazepines",
                "object": "vascular dementia",
                "search_query": "Sleeping pills such as benzodiazepines have no effect on vascular dementia."
            }
        ]
    }
]

# Claim decomposition prompt
claim_decomposition_prompt = f"""
You are given a problem description and a claim. Split the claim into atomic predicates (extracting BOTH factual assertions and subjective opinions) and return only structured predicate objects.

Important:
- EMPTY/FRAGMENTS: If the input is a single word, purely conversational, or a verb-less fragment (e.g., "wtf", "hello", "penicillin"), return an empty list `[]`. Do NOT guess or hallucinate facts from prompt examples.
- ATOMICITY: Prefer 1 factual statement per subclaim. If the claim is compound, produce one subclaim for each independently checkable fact. Keep each predicate minimal (one fact per item). Do not group distinct subjects or objects. Split compound/conjunctive claims into multiple subclaims. Each subclaim MUST contain exactly one independently verifiable fact.
- VERBATIM EXTRACTION (CRITICAL): Maintain the EXACT terminology used in the original text for clinical conditions, treatments, and technologies. DO NOT use generic synonyms or acronyms (e.g., do not translate "Magnetic resonance therapy" to "MRI"). Keep the original clinical words intact to avoid semantic drift during document retrieval. Extract EXACTLY what is asserted, even if false. Do NOT auto-correct or add external info. Do not invent facts.
- EXTRACT EVERYTHING: Include subjective opinions, anecdotal reports, and recommendations. The downstream classifier will filter them.

Structural rules:
- CONDITIONALS & EXCEPTIONS: If a fact has a premise ("if X", "unless Y"), incorporate it into EACH derived subclaim (e.g., "in patients with X", "in patients without Y"). CRITICAL: Carry the condition into ALL trailing clauses ("as it may lead to Z").
- ALTERNATIVES: For "only if X; otherwise Y", split into "action if X" and "action if NOT X".
- DISJUNCTIONS: "X or Y" becomes two subclaims (one for X, one for Y).
- COREFERENCE: Name entities explicitly. Resolve ALL pronouns ("it", "this treatment") to the exact nouns.
- ATTRIBUTIONS: If a claim is an opinion/rumor ("people say X"), include the attribution ("people say") in the subclaim.
- BACKGROUND FACTS: Extract embedded contextual facts (e.g., "Despite the lawsuit..." -> "There is a lawsuit").

Content rules:
- EXHAUSTIVE EXTRACTION: Process ALL sentences and clauses in the input. Do not stop early. If there are multiple separate questions or statements, you MUST extract subclaims for EVERY single one of them.
- SPLIT CONJUNCTIONS/DISJUNCTIONS: Always split "X or Y" and "X and Y" into two separate predicates. If the claim is "X and Y cause Z", you MUST output "X causes Z" and "Y causes Z". Never leave an "or" / "and" grouping distinct subjects or objects in a single subclaim.
- CRITICAL: The `search_query` MUST be a positive, declarative statement. NEVER output a question. If the input is a question (e.g., "Does X cure Y?"), you MUST convert it into a declarative statement ("X cures Y"). NEVER include a question mark (?).
- CRITICAL: Output valid JSON using DOUBLE QUOTES (") for strings.
- Prefer explicit subjects and normalized nouns. Use active voice.

Return the result in JSON format, as shown in the example below.
Here are examples:
{claim_decomposition_examples}

Important output constraint:
- The function call arguments must contain only the schema fields defined above.
"""

# Claim classification response schema
claim_classification = {
    "name": "claim_classification",
    "description": "Classifies predicates as either 'verifiable' or 'non-verifiable'.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "thought_process": {
                "type": "string",
                "description": "Analyze each query to determine if it asserts a checkable medical fact, a subjective opinion, or an out-of-domain fact."
            },
            "predicate_type_dict": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The natural language query being classified."
                        },
                        "type": {
                            "type": "string",
                            "enum": ["verifiable", "non-verifiable", "out-of-domain"],
                            "description": "Classification type of the subclaim."
                        }
                    },
                    "required": ["query", "type"],
                    "additionalProperties": False
                },
                "description": "A list of predicates with their classification types."
            }
        },
        "additionalProperties": False,
        "required": ["thought_process", "predicate_type_dict"]
    }
}

# Claim classification prompt
claim_classification_prompt = f"""
You are an expert in claim verification. Your task is to determine whether each query is VERIFIABLE, NON-VERIFIABLE, or OUT-OF-DOMAIN.

## Definition
A VERIFIABLE claim is any factual assertion about the world that could, in principle, be checked against objective evidence (scientific studies, databases, official records, measurements). It does NOT matter whether the claim is true, false, controversial, or about an obscure topic — only whether evidence could confirm or refute it. IMPORTANT: For this task, it MUST be related to medicine, health, biology, or clinical practice.

A NON-VERIFIABLE claim is ONLY one that:
- Expresses a purely subjective opinion or personal preference ("X is the best", "I believe...", "the most elegant breakthrough")
- Is an anecdotal, vague, or purely qualitative report lacking clinical metrics (e.g., "patients generally report feeling more energetic", "everyone online says")
- Relies on idioms, metaphors, or vague hyperboles (e.g., "makes your wallet lighter", "a mystical healing process")
- Is so vague that no specific fact can be checked

An OUT-OF-DOMAIN claim is one that:
- Is a verifiable fact, but has absolutely nothing to do with medical science, health, human biology, or clinical practice (e.g., software engineering, IT, pop culture, general history, geography, entertainment, corporate financial/stock data, revenue drops, or legal disputes). Even if a pharmaceutical company is mentioned, pure financial or legal facts are OUT-OF-DOMAIN.

## Critical rules — do NOT make these mistakes:
- CLINICAL RECOMMENDATIONS / NECESSITY: Claims stating a medical treatment or action is "necessary", "recommended", or "should be done" are VERIFIABLE if they imply a standard of care or clinical efficacy (e.g., "Booster doses are necessary to maintain protection" -> VERIFIABLE).
- SAFETY CLAIMS: Statements asserting that a drug, treatment, or substance is "safe" or "unsafe" are VERIFIABLE since safety, tolerability, and adverse effects are checked against clinical studies (e.g., "It is safe to take isotretinoin during pregnancy" -> VERIFIABLE).
- A claim with a NEGATION is still verifiable ("X does NOT cause Y" → VERIFIABLE)
- A claim about an OBSCURE or CONTROVERSIAL product is still verifiable ("The Zisano bracelet strengthens the immune system" → VERIFIABLE)
- A claim phrased as a QUESTION is still verifiable ("Does X treat Y?" → VERIFIABLE)
- A claim about a medical ASSOCIATION or RISK is still verifiable ("X increases the risk of Y" → VERIFIABLE)
- A claim you personally doubt or find implausible is still verifiable if it asserts a checkable fact
- DEFAULT TO OUT-OF-DOMAIN FOR NON-MEDICAL FACTS: If a fact is verifiable but you are unsure if it is medical enough, classify it as OUT-OF-DOMAIN. Only classify as VERIFIABLE if it clearly relates to medicine, biology, or health.

## Examples of VERIFIABLE claims (Medical/Health):
- "Booster doses are necessary to maintain optimal protection against COVID-19." (Medical necessity/recommendation)
- "St. John's wort relieves the symptoms of depression." (Medical claim)
- "Is Trastuzumab (Herceptin) of potential use in the treatment of prostate cancer?" (Question form)
- "Thigh-length graduated compression stockings did not reduce deep vein thrombosis." (Negation)
- "The Zisano bracelet strengthens the immune system." (Obscure health product)

## Examples of NON-VERIFIABLE claims:
- "Climate change is the most important issue facing humanity today." (Subjective opinion)
- "Medical research should receive more funding because health is the most important thing." (Subjective value statement)
- "Leading experts feel the new mRNA vaccine is the most elegant medical breakthrough of our generation." (Vague qualitative opinion)
- "Patients generally report feeling more energetic after the second dose." (Anecdotal / lacking metrics)

## Examples of OUT-OF-DOMAIN claims:
- "The average global temperature increased by 0.8°C between 1880 and 2012." (Verifiable, but general science/climate, not medical)
- "The film Parasite won the Academy Award for Best Picture in 2020." (Verifiable, but entertainment)
- "Geolier has written the song Soldati." (Verifiable, but music/pop culture)
- "AWS S3 storage fees have recently increased by 15%." (Verifiable, but technology/business)
- "The new software update reduces ETL pipeline execution time by 40%." (Verifiable, but software engineering/IT)

Classify each query only by whether it can be checked against objective evidence. Do not judge usefulness, plausibility, importance, or desirability. Do not rewrite the query; only assign a label.

CRITICAL RULES FOR JSON OUTPUT:
1. You must output valid JSON using DOUBLE QUOTES (") for all string keys and values.
2. The `query` field in your output MUST be an exact, character-for-character copy of the input query. NEVER substitute the query with an example from this prompt. If the input query is "ciao", the output query MUST be "ciao".

Here is an example of the expected JSON output format:
{{
    "thought_process": "1. 'Booster doses are necessary...' is a clinical recommendation regarding vaccine efficacy, which can be checked against scientific consensus, so it is 'verifiable'. 2. 'AWS S3 storage fees...' is a factual statement but belongs to cloud computing, so it is 'out-of-domain'. 3. 'Patients generally report feeling more energetic...' is purely anecdotal and lacks clinical metrics, so it is 'non-verifiable'.",
    "predicate_type_dict": [
        {{
            "query": "Booster doses are necessary to maintain optimal protection against COVID-19.",
            "type": "verifiable"
        }},
        {{
            "query": "AWS S3 storage fees have recently increased by 15%.",
            "type": "out-of-domain"
        }},
        {{
            "query": "Patients generally report feeling more energetic after the second dose.",
            "type": "non-verifiable"
        }}
    ]
}}
"""

