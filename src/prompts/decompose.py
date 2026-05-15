# Claim decomposition response schema
claim_decomposition = { 
    "name": "claim_decomposition",
    "description": "Splits an input claim into multiple subclaims.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "predicates": {
                "type": "array",
                "minItems": 1,
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
                    "additionalProperties": False,
                    "required": ["relation", "subject", "object", "search_query"]
                },
                "description": "The structured predicates derived from the input claim."
            }
        },
        "additionalProperties": False,
        "required": ["predicates"]
    }
}

# Claim decomposition examples
claim_decomposition_examples = [
    {
        "input_claim": "Howard University Hospital and Providence Hospital are both located in Washington, D.C.",
        "predicates": [
            {
                "relation": "Location",
                "subject": "Howard University Hospital",
                "object": "Washington, D.C.",
                "search_query": "Verify that Howard University Hospital is located in Washington, D.C."
            },
            {
                "relation": "Location",
                "subject": "Providence Hospital",
                "object": "Washington, D.C.",
                "search_query": "Verify that Providence Hospital is located in Washington, D.C."
            }
        ],
    },
    {
        "input_claim": "In 1959, former Chilean boxer Alfredo Cornejo Cuevas (born June 6, 1933) won the gold medal in the welterweight division at the Pan American Games (held in Chicago, United States, from August 27 to September 7) in Chicago, United States, and the world amateur welterweight title in Mexico City.",
        "predicates": [
            {
                "relation": "Born",
                "subject": "Alfredo Cornejo Cuevas",
                "object": "June 6, 1933",
                "search_query": "Verify that Alfredo Cornejo Cuevas was born on June 6, 1933."
            },
            {
                "relation": "Won",
                "subject": "Alfredo Cornejo Cuevas",
                "object": "the gold medal in the welterweight division at the Pan American Games in 1959",
                "search_query": "Verify that Alfredo Cornejo Cuevas won the gold medal in the welterweight division at the Pan American Games in 1959."
            },
            {
                "relation": "Held",
                "subject": "The Pan American Games in 1959",
                "object": "Chicago, United States",
                "search_query": "Verify that the Pan American Games in 1959 were held in Chicago, United States."
            },
            {
                "relation": "Won",
                "subject": "Alfredo Cornejo Cuevas",
                "object": "the world amateur welterweight title in Mexico City",
                "search_query": "Verify that Alfredo Cornejo Cuevas won the world amateur welterweight title in Mexico City."
            }
        ],
    },
    {
        "input_claim": "Daily vitamin D supplementation reduces the risk of osteoporosis in postmenopausal women, but it should be avoided in people with kidney stones to prevent worsening nephrolithiasis.",
        "predicates": [
            {
                "relation": "ReduceRisk",
                "subject": "Daily vitamin D supplementation",
                "object": "osteoporosis in postmenopausal women",
                "search_query": "Verify that daily vitamin D supplementation reduces the risk of osteoporosis in postmenopausal women."
            },
            {
                "relation": "Avoid",
                "subject": "People with kidney stones",
                "object": "daily vitamin D supplementation",
                "search_query": "Verify that people with kidney stones should avoid daily vitamin D supplementation to prevent worsening nephrolithiasis."
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
- Ignore subjective opinions, recommendations, and normative fragments that are not factual claims.
- Do not turn a recommendation into a factual predicate.

Formatting rules:
- Return a JSON object with one key: "predicates".
- Do not include "input_claim", "claim", or any other metadata key in the output.
- Each item in "predicates" must contain exactly four fields: relation, subject, object, search_query.
- The relation should be a short predicate label in TitleCase.
- The subject and object should be normalized noun phrases.
- The search_query should be a concise, grammatical verification query.
- Use active voice and correct English (e.g., "people with kidney stones should avoid ...").
- Prefer normalized nouns over gerunds (e.g., "daily vitamin D supplementation" over "taking a daily vitamin D supplement").
- Prefer explicit subjects (e.g., "people with kidney stones" over "those").
- Keep each predicate minimal (one fact per item).
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
                        "predicate": {
                            "type": "object",
                            "properties": {
                                "relation": {"type": "string"},
                                "subject": {"type": "string"},
                                "object": {"type": "string"},
                                "search_query": {"type": "string"}
                            },
                            "additionalProperties": False,
                            "required": ["relation", "subject", "object", "search_query"]
                        },
                        "type": {
                            "type": "string",
                            "enum": ["verifiable", "non-verifiable"],
                            "description": "Classification type of the subclaim."
                        }
                    },
                    "required": ["predicate", "type"],
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
You are an expert in claim verification. Your task is to determine whether each predicate is verifiable or non-verifiable.
A verifiable claim is a factual statement that can be checked against objective evidence from reliable sources. It makes specific assertions about the world that can be proven true or false through investigation.

A non-verifiable claim is one that cannot be objectively verified because it:
- Expresses a subjective opinion, preference, or personal experience  
- Makes vague or ambiguous statements without specific details  
- Refers to future events that haven't occurred yet  
- Makes normative or ethical judgments about what "should" be  
- Contains hypothetical scenarios or counterfactuals  

### Examples:
Verifiable: "The average global temperature increased by 0.8$^\circ$C between 1880 and 2012." 
Non-verifiable: "Climate change is the most important issue facing humanity today."  
Verifiable: "The film 'Parasite' won the Academy Award for Best Picture in 2020."  
Non-verifiable: "Parasite deserved to win the Academy Award for Best Picture."

Please analyze the following predicates and classify each one as either VERIFIABLE or NON-VERIFIABLE. Return only structured predicate classifications.
"""

# Claim splitting response schema
claim_splitting = {
    "name": "claim_splitting",
    "description": "Verifiable subclaims only",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "subclaims": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The verifiable subclaims after filtering out non-verifiable subclaims"
            }
        },
        "additionalProperties": False,
        "required": ["subclaims"]
    }
}

# Claim splitting prompt
claim_splitter_prompt = "Filter out the non-verifiable claims. If there is no verifiable fact, return NON-SUPPORTED."