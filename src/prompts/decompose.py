# Claim decomposition response schema
claim_decomposition = { 
    "name": "claim_decomposition",
    "description": "Splits an input claim into multiple subclaims.", # Description is passed to the LLM to help it understand the purpose of the function
    "strict": True, # Enforce that the output strictly adheres to the defined schema, with no extra fields or missing required fields
    "parameters": { # Define the structure of the expected output from the LLM
        "type": "object", # The output should be a JSON object
        "properties": {
            "predicates": { 
                "type": "array",
                "minItems": 1, # Ensure at least one predicate is returned for claims with factual content
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
                            "description": "A concise query to verify the predicate."
                        }
                    },
                    "additionalProperties": False, # Ensure no extra fields are included in each predicate object
                    "required": ["relation", "subject", "object", "search_query"]
                },
                "description": "The structured predicates derived from the input claim."
            }
        },
        "additionalProperties": False, # Ensure no extra fields are included in the main object
        "required": ["predicates"]
    }
}



# Claim decomposition examples
claim_decomposition_examples = [
    {
        "input_claim": "Howard University Hospital is located in Washington, D.C., and Providence Hospital is located in Washington, D.C.",
        "predicates": [
            {
                "relation": "Location",
                "subject": "Howard University Hospital",
                "object": "Washington, D.C.",
                "search_query": "Howard University Hospital is located in Washington, D.C."
            },
            {
                "relation": "Location",
                "subject": "Providence Hospital",
                "object": "Washington, D.C.",
                "search_query": "Providence Hospital is located in Washington, D.C."
            }
        ],
    },
    {
        "input_claim": "Alfredo Cornejo Cuevas was born on June 6, 1933. He won the gold medal in the welterweight division at the 1959 Pan American Games in Chicago, United States. The 1959 Pan American Games were held in Chicago, United States. He also won the world amateur welterweight title in Mexico City.",
        "predicates": [
            {
                "relation": "Born",
                "subject": "Alfredo Cornejo Cuevas",
                "object": "June 6, 1933",
                "search_query": "Alfredo Cornejo Cuevas was born on June 6, 1933."
            },
            {
                "relation": "Won",
                "subject": "Alfredo Cornejo Cuevas",
                "object": "the gold medal in the welterweight division at the Pan American Games in 1959",
                "search_query": "Alfredo Cornejo Cuevas won the gold medal in the welterweight division at the Pan American Games in 1959."
            },
            {
                "relation": "Held",
                "subject": "The Pan American Games in 1959",
                "object": "Chicago, United States",
                "search_query": "The Pan American Games in 1959 were held in Chicago, United States."
            },
            {
                "relation": "Won",
                "subject": "Alfredo Cornejo Cuevas",
                "object": "the world amateur welterweight title in Mexico City",
                "search_query": "Alfredo Cornejo Cuevas won the world amateur welterweight title in Mexico City."
            }
        ],
    },
    {
        "input_claim": "Daily vitamin D supplementation reduces the risk of osteoporosis in postmenopausal women, and people with kidney stones are sometimes advised to avoid it because it can worsen nephrolithiasis.",
        "predicates": [
            {
                "relation": "ReduceRisk",
                "subject": "Daily vitamin D supplementation",
                "object": "osteoporosis in postmenopausal women",
                "search_query": "Daily vitamin D supplementation reduces the risk of osteoporosis in postmenopausal women."
            },
            {
                "relation": "Avoid",
                "subject": "People with kidney stones",
                "object": "daily vitamin D supplementation",
                "search_query": "People with kidney stones should avoid daily vitamin D supplementation to prevent worsening nephrolithiasis."
            }
        ],
    },
    {
        "input_claim": "The treatment may help in some cases.",
        "predicates": [
            {
                "relation": "Claim",
                "subject": "The treatment may help in some cases",
                "object": "The treatment may help in some cases",
                "search_query": "The treatment may help in some cases."
            }
        ],
    },
    {
        "input_claim": "Does the Mediterranean diet improve cardiovascular health? Can it reduce the risk of heart attacks?",
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
        ],
    },
    {
        "input_claim": "If the patient presents with an EGFR gene mutation or an ALK translocation, non-small cell lung cancer (NSCLC) responds positively to targeted molecular therapies, although acquired resistance may develop within 10-14 months of starting treatment.",
        "predicates": [
            {
                "relation": "Responds",
                "subject": "NSCLC with EGFR gene mutation",
                "object": "targeted molecular therapies",
                "search_query": "NSCLC responds positively to targeted molecular therapies in patients with an EGFR gene mutation."
            },
            {
                "relation": "Responds",
                "subject": "NSCLC with ALK translocation",
                "object": "targeted molecular therapies",
                "search_query": "NSCLC responds positively to targeted molecular therapies in patients with an ALK translocation."
            },
            {
                "relation": "Develop",
                "subject": "Acquired resistance to targeted molecular therapies in NSCLC",
                "object": "within 10-14 months of starting treatment",
                "search_query": "Acquired resistance to targeted molecular therapies in NSCLC may develop within 10-14 months of starting treatment."
            }
        ],
    },
]

# Claim decomposition prompt
claim_decomposition_prompt = f"""
You are given a problem description and a claim. Split the claim into atomic, verifiable predicates and return only structured predicate objects.

Important:
- Never return an empty list when the claim contains factual content.
- Split conjunctive claims into separate subclaims.
- Keep each subclaim grounded in the original claim; do not invent new facts or overgeneralize.
- Prefer 1 factual statement per subclaim.
- If the claim is compound, produce one subclaim for each independently checkable fact.
- If the claim is ambiguous, underspecified, or not safely splittable, return the original claim as a single subclaim instead of forcing a decomposition.
- Ignore subjective opinions, recommendations, and normative fragments that are not factual claims.
- Do not turn a recommendation into a factual predicate.

Structural rules:
- CONDITIONALS: If a fact is conditioned on a premise ("if X then Y", "when X", "in patients with X"), incorporate the condition INTO each derived subclaim. Never extract the condition as a standalone predicate. Example: "If EGFR is mutated, NSCLC responds to therapy" becomes "NSCLC responds to therapy in patients with EGFR mutation" — NOT two separate claims.
- DISJUNCTIONS: If a claim contains "X or Y", split into separate subclaims — one for X and one for Y — each carrying the full surrounding context. Example: "EGFR mutation or ALK translocation" becomes two subclaims, one about EGFR and one about ALK.
- COREFERENCE: Every subclaim must name the disease, treatment, and population explicitly. Never use "the treatment", "those affected", or "it" — replace with the actual entity from the original claim.

Content rules:
- Keep each predicate minimal: one fact per item.
- Break down the original claim into multiple, atomic subclaims that can each be independently verified.
- The subclaims MUST be natural language sentences, formulated as statements (not questions).
- The subclaims must be completely self-contained. Resolve any pronouns (e.g. "it", "they") to the original entities.
- Ensure you extract all the assertions in the claim, no matter how small.
- Do NOT add external information that is not present in the original claim.
- CRITICAL: You must output valid JSON using DOUBLE QUOTES (") for all string keys and values. Never use single quotes to enclose strings.
- When using the fallback, preserve the original claim wording as closely as possible.
- Use active voice and correct English.
- Prefer normalized nouns over gerunds (e.g., "daily vitamin D supplementation" over "taking a daily vitamin D supplement").
- Prefer explicit subjects (e.g., "people with kidney stones" over "those").
- Avoid vague wording, pronouns without referents, and "should be avoided by" phrasing.

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
                            "enum": ["verifiable", "non-verifiable"],
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
        "required": ["predicate_type_dict"]
    }
}

# Claim classification prompt
claim_classification_prompt = f"""
You are an expert in claim verification. Your task is to determine whether each query is VERIFIABLE or NON-VERIFIABLE.

## Definition
A VERIFIABLE claim is any factual assertion about the world that could, in principle, be checked against objective evidence (scientific studies, databases, official records, measurements). It does NOT matter whether the claim is true, false, controversial, or about an obscure topic — only whether evidence could confirm or refute it.

A NON-VERIFIABLE claim is ONLY one that:
- Expresses a purely subjective opinion or personal preference ("X is the best", "I believe...")
- Makes a normative or ethical judgment about what "should" be done
- States a recommendation without attributing it to a source
- Is so vague that no specific fact can be checked

## Critical rules — do NOT make these mistakes:
- A claim with a NEGATION is still verifiable ("X does NOT cause Y" → VERIFIABLE)
- A claim about an OBSCURE or CONTROVERSIAL product is still verifiable ("The Zisano bracelet strengthens the immune system" → VERIFIABLE)
- A claim phrased as a QUESTION is still verifiable ("Does X treat Y?" → VERIFIABLE)
- A claim about a medical ASSOCIATION or RISK is still verifiable ("X increases the risk of Y" → VERIFIABLE)
- A claim you personally doubt or find implausible is still verifiable if it asserts a checkable fact
- When in doubt, classify as VERIFIABLE. Most factual claims about the physical world, medical treatments, and scientific findings ARE verifiable.

## Examples:
Verifiable: "The average global temperature increased by 0.8°C between 1880 and 2012."
Verifiable: "The film Parasite won the Academy Award for Best Picture in 2020."
Verifiable: "The 1959 Pan American Games were held in Chicago, United States."
Verifiable: "St. John's wort relieves the symptoms of depression."
Verifiable: "Is St. John's wort similarly effective as antidepressants?"
Verifiable: "Does metformin interfere with thyroxine absorption?"
Verifiable: "The F.X. Mayr cure has health benefits."
Verifiable: "The F.X. Mayr cure can prevent diseases."
Verifiable: "The Zisano bracelet strengthens the immune system."
Verifiable: "The Zisano bracelet reduces fatigue."
Verifiable: "Transplanted human glial progenitor cells are incapable of forming a neural network with host neurons."
Verifiable: "Angiotensin converting enzyme inhibitors are associated with increased risk for functional renal insufficiency."
Verifiable: "Is Trastuzumab (Herceptin) of potential use in the treatment of prostate cancer?"
Verifiable: "Is irritable bowel syndrome more common in women with endometriosis?"
Verifiable: "Thigh-length graduated compression stockings did not reduce deep vein thrombosis in stroke patients."
Non-verifiable: "Climate change is the most important issue facing humanity today."
Non-verifiable: "Parasite deserved to win the Academy Award for Best Picture."
Non-verifiable: "People with kidney stones should avoid daily vitamin D supplementation."
Non-verifiable: "Everyone ought to exercise more."

Classify each query only by whether it can be checked against objective evidence. Do not judge usefulness, plausibility, importance, or desirability. Do not rewrite the query; only assign a label.

CRITICAL: You must output valid JSON using DOUBLE QUOTES (") for all string keys and values. Never use single quotes to enclose strings.
"""

