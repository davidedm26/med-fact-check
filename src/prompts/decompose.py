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
        "input_claim": "Alfredo Cornejo Cuevas was born on June 6, 1933. He won the gold medal in the welterweight division at the 1959 Pan American Games in Chicago, United States. The 1959 Pan American Games were held in Chicago, United States. He also won the world amateur welterweight title in Mexico City.",
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
        "input_claim": "Daily vitamin D supplementation reduces the risk of osteoporosis in postmenopausal women, and people with kidney stones are sometimes advised to avoid it because it can worsen nephrolithiasis.",
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
    {
        "input_claim": "The treatment may help in some cases.",
        "predicates": [
            {
                "relation": "Claim",
                "subject": "The treatment may help in some cases",
                "object": "The treatment may help in some cases",
                "search_query": "Verify that the treatment may help in some cases."
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

Content rules:
- Keep each predicate minimal: one fact per item.
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

Classify each predicate only by whether it can be checked against objective evidence. Do not judge usefulness, plausibility, importance, or desirability. Do not rewrite the predicate; only assign a label.

A non-verifiable claim is one that cannot be objectively verified because it:
- Expresses a subjective opinion, preference, or personal experience  
- Makes vague or ambiguous statements without specific details  
- Refers to future events that haven't occurred yet  
- Makes normative or ethical judgments about what "should" be  
- Contains hypothetical scenarios or counterfactuals  
- States a recommendation or preference without attributing it to a checkable source

### Examples:
Verifiable: "The average global temperature increased by 0.8$^\circ$C between 1880 and 2012." 
Non-verifiable: "Climate change is the most important issue facing humanity today."  
Verifiable: "The film 'Parasite' won the Academy Award for Best Picture in 2020."  
Non-verifiable: "Parasite deserved to win the Academy Award for Best Picture."
Verifiable: "The 1959 Pan American Games were held in Chicago, United States."
Non-verifiable: "People with kidney stones should avoid daily vitamin D supplementation."
Verifiable: "The article states that people with kidney stones should avoid daily vitamin D supplementation."

Please analyze the following predicates and classify each one as either VERIFIABLE or NON-VERIFIABLE. Return only structured predicate classifications.
"""

