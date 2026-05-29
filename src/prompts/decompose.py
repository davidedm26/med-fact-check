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
        "input_claim": "Despite the regulator's recent ban, their latest compound saw a drop in sales.",
        "predicates": [
            {
                "relation": "Ban",
                "subject": "The regulator",
                "object": "the latest compound",
                "search_query": "There is a recent ban by the regulator."
            },
            {
                "relation": "Drop",
                "subject": "The regulator's latest compound",
                "object": "sales",
                "search_query": "The regulator's latest compound saw a drop in sales."
            }
        ],
    },
    {
        "input_claim": "ciao / hello there! wtf",
        "predicates": []
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
    {
        "input_claim": "Metformin is recommended as a first-line pharmacological treatment for type 2 diabetes mellitus, unless the patient has severe renal impairment (eGFR < 30 mL/min) or a history of lactic acidosis, in which case DPP-4 inhibitors should be considered instead.",
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
        ],
    },
    {
        "input_claim": "Patients with acute ischemic stroke should receive intravenous alteplase within 4.5 hours of symptom onset, but only if their blood pressure is strictly maintained below 185/110 mmHg; otherwise, mechanical thrombectomy is preferred.",
        "predicates": [
            {
                "relation": "Recommended",
                "subject": "intravenous alteplase",
                "object": "within 4.5 hours of symptom onset",
                "search_query": "Patients with acute ischemic stroke should receive intravenous alteplase within 4.5 hours of symptom onset if their blood pressure is maintained below 185/110 mmHg."
            },
            {
                "relation": "Recommended",
                "subject": "mechanical thrombectomy",
                "object": "patients with acute ischemic stroke",
                "search_query": "Mechanical thrombectomy is preferred for patients with acute ischemic stroke within 4.5 hours of symptom onset if their blood pressure is NOT maintained below 185/110 mmHg."
            }
        ],
    },
    {
        "input_claim": "The actor Tom Hanks won an Oscar in 1994, and recently he stated that daily aspirin prevents heart attacks in healthy adults.",
        "predicates": [
            {
                "relation": "Won",
                "subject": "The actor Tom Hanks",
                "object": "an Oscar in 1994",
                "search_query": "The actor Tom Hanks won an Oscar in 1994."
            },
            {
                "relation": "Prevents",
                "subject": "Daily aspirin",
                "object": "heart attacks in healthy adults",
                "search_query": "Daily aspirin prevents heart attacks in healthy adults."
            }
        ],
    },
    {
        "input_claim": "Although the manufacturer's stock price surged by 18% on the Nasdaq last week, their new monoclonal antibody reduces amyloid plaque buildup in Alzheimer's patients by 25%, an achievement that is widely felt to be the most magical scientific triumph of our era.",
        "predicates": [
            {
                "relation": "Surged",
                "subject": "The manufacturer's stock price",
                "object": "by 18% on the Nasdaq last week",
                "search_query": "The manufacturer's stock price surged by 18% on the Nasdaq last week."
            },
            {
                "relation": "Reduces",
                "subject": "The new monoclonal antibody",
                "object": "amyloid plaque buildup in Alzheimer's patients by 25%",
                "search_query": "The new monoclonal antibody reduces amyloid plaque buildup in Alzheimer's patients by 25%."
            },
            {
                "relation": "Felt to be",
                "subject": "The reduction of amyloid plaque buildup by the new monoclonal antibody",
                "object": "the most magical scientific triumph of our era",
                "search_query": "The reduction of amyloid plaque buildup by the new monoclonal antibody is widely felt to be the most magical scientific triumph of our era."
            }
        ],
    },
    {
        "input_claim": "Following the Ministry of Health's unexpected budget cuts, clinicians are now instructed to prescribe generic amoxicillin instead of targeted cephalosporins unless the patient has a documented penicillin allergy or severe hepatic failure, a policy shift that local tabloids call a murderous attack on the poor.",
        "predicates": [
            {
                "relation": "Budget cuts",
                "subject": "The Ministry of Health",
                "object": "unexpected budget cuts",
                "search_query": "There are unexpected budget cuts by the Ministry of Health."
            },
            {
                "relation": "Instructed to prescribe",
                "subject": "Clinicians",
                "object": "generic amoxicillin",
                "search_query": "Clinicians are instructed to prescribe generic amoxicillin in patients without a documented penicillin allergy."
            },
            {
                "relation": "Instructed to prescribe",
                "subject": "Clinicians",
                "object": "generic amoxicillin",
                "search_query": "Clinicians are instructed to prescribe generic amoxicillin in patients without severe hepatic failure."
            },
            {
                "relation": "Instructed to prescribe",
                "subject": "Clinicians",
                "object": "targeted cephalosporins",
                "search_query": "Clinicians are instructed to prescribe targeted cephalosporins if the patient has a documented penicillin allergy."
            },
            {
                "relation": "Instructed to prescribe",
                "subject": "Clinicians",
                "object": "targeted cephalosporins",
                "search_query": "Clinicians are instructed to prescribe targeted cephalosporins if the patient has severe hepatic failure."
            },
            {
                "relation": "Call",
                "subject": "Local tabloids",
                "object": "the policy shift a murderous attack on the poor",
                "search_query": "Local tabloids call the policy shift to prescribe generic amoxicillin instead of targeted cephalosporins a murderous attack on the poor."
            }
        ],
    },
]

# Claim decomposition prompt
claim_decomposition_prompt = f"""
You are given a problem description and a claim. Split the claim into atomic predicates (extracting BOTH factual assertions and subjective opinions) and return only structured predicate objects.

Important:
- EMPTY/GIBBERISH CLAIMS: If the input claim is meaningless, purely conversational, or contains no extractable assertions (e.g., "wtf", "hello"), you MUST return an empty list `[]` for predicates. Do NOT hallucinate facts from the examples.
- Never return an empty list when the claim contains factual content.
- Split conjunctive claims into separate subclaims.
- Keep each subclaim grounded in the original claim; do not invent new facts or overgeneralize.
- STRICT FAITHFULNESS: Extract EXACTLY what the claim asserts, even if you know it is factually incorrect, absurd, or false. Do NOT auto-correct the claim or substitute entities with the 'correct' real-world facts (e.g., if the claim says 'X invented Y', do not replace 'X' with the actual inventor).
- Prefer 1 factual statement per subclaim.
- If the claim is compound, produce one subclaim for each independently checkable fact.
- If the claim is ambiguous, underspecified, or not safely splittable, return the original claim as a single subclaim instead of forcing a decomposition.
- EXTRACT EVERYTHING: Extract ALL assertions from the text, including subjective opinions, anecdotal reports, recommendations, and normative statements. Do not filter them out during decomposition. The downstream classifier will decide if they are verifiable or not.

Structural rules:
- CONDITIONALS: If a fact is conditioned on a premise ("if X then Y", "when X", "in patients with X"), incorporate the condition INTO each derived subclaim. Never extract the condition as a standalone predicate. Example: "If EGFR is mutated, NSCLC responds to therapy" becomes "NSCLC responds to therapy in patients with EGFR mutation" — NOT two separate claims.
- EXCEPTIONS: If a claim contains an exception ("unless X", "except in Y"), convert it into a negative condition ("in patients without X") and attach it to the main claim. If the exception has an alternative ("unless X, in which case Z"), extract the main claim with the negative condition ("in patients without X") AND extract the alternative with the positive condition ("Z if the patient has X").
- ALTERNATIVES ("otherwise"): If a claim specifies a strict condition and an alternative ("only if X; otherwise Y"), split into two claims: the main action with the positive condition ("if X"), and the alternative Y with the INVERTED condition ("if NOT X"). Ensure both claims retain the full context.
- DISJUNCTIONS: If a claim contains "X or Y", split into separate subclaims — one for X and one for Y — each carrying the full surrounding context. Example: "EGFR mutation or ALK translocation" becomes two subclaims, one about EGFR and one about ALK.
- COREFERENCE: Every subclaim must name the entities explicitly. Resolve ALL pronouns ("it", "they", "their", "this") and abstract references ("the treatment", "the company", "this outcome", "an achievement") to the exact nouns or full events from the original claim.
- BACKGROUND FACTS: Extract embedded facts even if they are presented as noun phrases or contextual background (e.g., "Despite the lawsuit..." -> "There is a lawsuit..."). Treat them as independent assertions.

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
        "required": ["predicate_type_dict"]
    }
}

# Claim classification prompt
claim_classification_prompt = f"""
You are an expert in claim verification. Your task is to determine whether each query is VERIFIABLE or NON-VERIFIABLE.

## Definition
A VERIFIABLE claim is any factual assertion about the world that could, in principle, be checked against objective evidence (scientific studies, databases, official records, measurements). It does NOT matter whether the claim is true, false, controversial, or about an obscure topic — only whether evidence could confirm or refute it. IMPORTANT: For this task, it MUST be related to medicine, health, biology, or clinical practice.

A NON-VERIFIABLE claim is ONLY one that:
- Expresses a purely subjective opinion or personal preference ("X is the best", "I believe...", "the most elegant breakthrough")
- Makes a normative or ethical judgment about what "should" be done
- States a recommendation without attributing it to a source
- Is an anecdotal, vague, or purely qualitative report lacking clinical metrics (e.g., "patients generally report feeling more energetic")
- Is so vague that no specific fact can be checked

An OUT-OF-DOMAIN claim is one that:
- Is a verifiable fact, but has absolutely nothing to do with medical science, health, human biology, or clinical practice (e.g., pop culture, general history, geography, entertainment, corporate financial/stock data, revenue drops, or legal disputes). Even if a pharmaceutical company is mentioned, pure financial or legal facts are OUT-OF-DOMAIN.

## Critical rules — do NOT make these mistakes:
- A claim with a NEGATION is still verifiable ("X does NOT cause Y" → VERIFIABLE)
- A claim about an OBSCURE or CONTROVERSIAL product is still verifiable ("The Zisano bracelet strengthens the immune system" → VERIFIABLE)
- A claim phrased as a QUESTION is still verifiable ("Does X treat Y?" → VERIFIABLE)
- A claim about a medical ASSOCIATION or RISK is still verifiable ("X increases the risk of Y" → VERIFIABLE)
- A claim you personally doubt or find implausible is still verifiable if it asserts a checkable fact
- DEFAULT TO OUT-OF-DOMAIN FOR NON-MEDICAL FACTS: If a fact is verifiable but you are unsure if it is medical enough, classify it as OUT-OF-DOMAIN. Only classify as VERIFIABLE if it clearly relates to medicine, biology, or health.

## Examples of VERIFIABLE claims (Medical/Health):
- "St. John's wort relieves the symptoms of depression." (Medical claim)
- "Is Trastuzumab (Herceptin) of potential use in the treatment of prostate cancer?" (Question form)
- "Thigh-length graduated compression stockings did not reduce deep vein thrombosis." (Negation)
- "The Zisano bracelet strengthens the immune system." (Obscure health product)
- "The WHO recommends exclusive breastfeeding for the first six months." (Attributed health recommendation - checkable)

## Examples of NON-VERIFIABLE claims:
- "Climate change is the most important issue facing humanity today." (Subjective opinion)
- "People with kidney stones should avoid daily vitamin D supplementation." (Unattributed recommendation / normative)
- "Leading experts feel the new mRNA vaccine is the most elegant medical breakthrough of our generation." (Vague qualitative opinion)
- "Patients generally report feeling more energetic after the second dose." (Anecdotal / lacking metrics)

## Examples of OUT-OF-DOMAIN claims:
- "The average global temperature increased by 0.8°C between 1880 and 2012." (Verifiable, but general science/climate, not medical)
- "The film Parasite won the Academy Award for Best Picture in 2020." (Verifiable, but entertainment)
- "Geolier has written the song Soldati." (Verifiable, but music/pop culture)
- "AWS S3 storage fees have recently increased by 15%." (Verifiable, but technology/business)

Classify each query only by whether it can be checked against objective evidence. Do not judge usefulness, plausibility, importance, or desirability. Do not rewrite the query; only assign a label.

CRITICAL RULES FOR JSON OUTPUT:
1. You must output valid JSON using DOUBLE QUOTES (") for all string keys and values.
2. The `query` field in your output MUST be an exact, character-for-character copy of the input query. NEVER substitute the query with an example from this prompt. If the input query is "ciao", the output query MUST be "ciao".
"""

