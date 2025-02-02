import sys
import json
from mistralai import Mistral
import os
from Case_bank.Search import search
import time

def log_debug(message):
    try:
        with open('/tmp/debug.log', 'a') as f:
            f.write(f"{str(message)}\n")
    except Exception as e:
        print(f"ERROR: Failed to write to debug log: {str(e)}")

class ConversationManager:
    def __init__(self, api_key="9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"):
        try:
            self.client = Mistral(api_key=api_key)
        except Exception as e:
            log_debug(f"ERROR: Failed to initialize Mistral client: {str(e)}")
            raise

    def get_llm_response(self, history, state):
        try:
            # Prepare conversation context
            conversation_context = {
                "history": history[-3:],  # Last 3 messages for context
                "current_state": state,
                "missing_fields": [k for k, v in state.items() if v is None]
            }

            # Create dynamic prompt based on conversation state
            prompt = f"""You are an M&A advisor helping gather information about a potential transaction.

Current Information:
{json.dumps(conversation_context['current_state'], indent=2)}

Recent Conversation:
{json.dumps(conversation_context['history'], indent=2)}

Your task:
1. Analyze the conversation
2. Extract any new information
3. Engage naturally with the user
4. If information is missing, ask relevant follow-up questions
5. When sufficient information is gathered, indicate readiness for search

Return your response in this exact JSON format:
{{
    "response": "your natural response to the user",
    "extracted_info": {{
        "client_name": "extracted or null",
        "client_location": "extracted or null",
        "target_name": "extracted or null",
        "target_location": "extracted or null",
        "leading_partner": "extracted or null"
    }},
    "sufficient_info": boolean,
    "confidence": 0-100
}}"""

            # Get LLM response
            response = self.client.chat.complete(
                model="ft:open-mistral-7b:ef8d006f:20250129:34aed003",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )

            log_debug(f"Raw LLM response: {response.choices[0].message.content}")

            try:
                parsed_response = json.loads(response.choices[0].message.content)
                
                # Update state with any new information
                updated_state = state.copy()
                for key, value in parsed_response["extracted_info"].items():
                    if value and value.lower() != "null":
                        updated_state[key] = value

                # Calculate completion percentage
                filled_fields = sum(1 for v in updated_state.values() if v is not None and v != "")
                completion = min(100, (filled_fields / 3) * 100)  # Need at least 3 fields for 100%

                return {
                    "response": parsed_response["response"],
                    "updated_state": updated_state,
                    "completion_percentage": completion if not parsed_response["sufficient_info"] else 100
                }

            except json.JSONDecodeError as e:
                log_debug(f"JSON Parse Error: {e}")
                # Try to extract just the response if JSON parsing fails
                return {
                    "response": response.choices[0].message.content[:200],
                    "updated_state": state,
                    "completion_percentage": 0
                }

        except Exception as e:
            log_debug(f"ERROR in get_llm_response: {str(e)}")
            raise

def clear_old_sessions():
    """Clear session files older than 1 hour"""
    try:
        current_time = time.time()
        for filename in os.listdir('/tmp'):
            if filename.startswith('conversation_state_'):
                filepath = os.path.join('/tmp', filename)
                if os.path.getmtime(filepath) < current_time - 3600:  # 1 hour
                    os.remove(filepath)
    except Exception as e:
        log_debug(f"ERROR clearing old sessions: {str(e)}")

def get_default_state():
    return {
        "client_name": None,
        "client_location": None,
        "target_name": None,
        "target_location": None,
        "leading_partner": None
    }

def load_state(session_id):
    try:
        clear_old_sessions()  # Clean up old sessions
        state_file = f"/tmp/conversation_state_{session_id}.json"
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {"state": get_default_state(), "history": []}
                if "state" not in data:
                    data["state"] = get_default_state()
                if "history" not in data:
                    data["history"] = []
                return data
        return {"state": get_default_state(), "history": []}
    except Exception as e:
        log_debug(f"ERROR: Failed to load state: {str(e)}")
        return {"state": get_default_state(), "history": []}

def save_state(session_id, data):
    try:
        state_file = f"/tmp/conversation_state_{session_id}.json"
        with open(state_file, 'w') as f:
            json.dump(data, f)
        log_debug(f"Saved state: {json.dumps(data)}")
    except Exception as e:
        log_debug(f"ERROR: Failed to save state: {str(e)}")
        raise

def is_state_complete(state):
    """Check if we have enough useful information to proceed"""
    # Required fields (must have at least one of these pairs)
    required_pairs = [
        ("client_name", "target_name"),  # Need both client and target
    ]
    
    # Check if we have at least one complete pair
    has_required = any(
        state[pair[0]] is not None and state[pair[0]] != "" and
        state[pair[1]] is not None and state[pair[1]] != ""
        for pair in required_pairs
    )
    
    # Count how many fields have values
    filled_fields = sum(1 for value in state.values() if value is not None and value != "")
    
    # Consider state complete if we have the required pair and at least 3 fields total
    return has_required and filled_fields >= 3

def process_message(session_id, user_input):
    try:
        # Load state and history
        data = load_state(session_id)
        log_debug(f"Current state before processing: {json.dumps(data)}")
        
        # Add user input to history
        data["history"].append({
            "role": "user",
            "content": user_input
        })
        
        # Get LLM response
        manager = ConversationManager()
        llm_response = manager.get_llm_response(data["history"], data["state"])

        if not llm_response:
            raise Exception("Failed to get valid response from LLM")

        # Update state
        data["state"] = llm_response["updated_state"]
        
        # Check if state is complete
        complete = is_state_complete(data["state"])
        
        # Add LLM response to history
        data["history"].append({
            "role": "assistant",
            "content": llm_response["response"]
        })
        
        # Save updated data
        save_state(session_id, data)
        
        log_debug(f"State after processing: {json.dumps(data)}")
        log_debug(f"Complete: {complete}, Completion: {llm_response['completion_percentage']}")

        if complete:
            try:
                # Perform the search
                search_query = {
                    "client": data["state"]["client_name"],
                    "target": data["state"]["target_name"],
                    "transaction_type": data["state"]["leading_partner"] if data["state"]["leading_partner"] else "M&A"
                }
                log_debug(f"Performing search with query: {json.dumps(search_query)}")
                search_results = search(search_query)
                
                if search_results:
                    return {
                        "type": "search_results",
                        "message": "Here are the relevant documents I found:",
                        "results": search_results,
                        "progress": 100
                    }
                else:
                    log_debug("Search returned no results")
                    return {
                        "type": "conversation",
                        "message": "I searched our database but couldn't find any relevant documents. Would you like to know about specific aspects of this type of transaction?",
                        "progress": 100
                    }
                    
            except Exception as e:
                log_debug(f"Search failed: {str(e)}")
                return {
                    "type": "conversation",
                    "message": f"Search error: {str(e)}",
                    "progress": 75
                }
        
        return {
            "type": "conversation",
            "message": llm_response["response"],
            "progress": llm_response["completion_percentage"]
        }

    except Exception as e:
        log_debug(f"ERROR in process_message: {str(e)}")
        return {
            "type": "error",
            "message": f"ERROR: {str(e)}",
            "progress": 0
        }

def main():
    try:
        if len(sys.argv) < 3:
            raise ValueError("Missing required arguments")
        
        session_id = sys.argv[1]
        user_input = sys.argv[2]
        
        response = process_message(session_id, user_input)
        print(json.dumps(response))
        
    except Exception as e:
        error_response = {
            "type": "error",
            "message": f"ERROR: {str(e)}",
            "progress": 0
        }
        print(json.dumps(error_response))

if __name__ == "__main__":
    main() 