import json
import logging
import time
from huggingface_hub import InferenceClient

from src.prompts.retriever_agent_prompt import retriever_agent_prompt, retriever_agent_schema

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class RetrieverAgent:
    def __init__(self, hf_token: str):
        self.client = InferenceClient(
            model="meta-llama/Meta-Llama-3-8B-Instruct",
            token=hf_token
        )

    def generate_query(self, sub_claim_text: str) -> dict:
        compiled_prompt = retriever_agent_prompt.replace("{sub_claim_text}", sub_claim_text)
        
        # Instruction for the LLM
        system_message = (
            "You are a JSON-only API. Output ONLY the data object corresponding to the 'properties' "
            "of the following schema. DO NOT wrap it in a 'parameters' key.\n" 
            + json.dumps(retriever_agent_schema["parameters"]["properties"])
        )
        
        for attempt in range(3):
            try:
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": compiled_prompt}
                    ],
                    max_tokens=400,
                    temperature=0.1 
                )
                
                response_text = response.choices[0].message.content.strip()
                
                # 1. Clean Markdown wrappers
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                # 2. Extract raw JSON
                start = response_text.find('{')
                end = response_text.rfind('}')
                
                if start != -1 and end != -1:
                    json_str = response_text[start:end+1]
                    extracted_json = json.loads(json_str)
                    
                    
                    # If the LLM wraps the result inside "parameters", pull it out
                    if "parameters" in extracted_json and "search_queries" in extracted_json["parameters"]:
                        extracted_json = extracted_json["parameters"]
                    
                    # 3. Validate keys
                    if "search_queries" in extracted_json and "target_source" in extracted_json:
                        return extracted_json
                    else:
                        logging.warning(f"[HF] JSON missing required keys. Retrying...")
                        
            except Exception as e:
                if "429" in str(e):
                    wait_time = 5 * (attempt + 1)
                    logging.warning(f"[HuggingFace Quota] Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logging.warning(f"[HF Parsing Error] {e}. Retrying...")
                continue
                
        # Fallback
        logging.error(f"🔴 [RetrieverAgent] Total LLM failure for claim: '{sub_claim_text}'.")
        return {
            "reasoning": "CRITICAL ERROR: The LLM did not respond correctly after 3 attempts or the APIs are offline.",
            "target_source": "literature", 
            "search_queries": [] 
        }