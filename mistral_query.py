import sys
import time
import random
from mistralai import Mistral

# Your Fine-Tuned Model ID (replace with the actual model ID)
FINE_TUNED_MODEL_ID = "ft:open-mistral-7b:ef8d006f:20250129:34aed003"

# API key and fine-tuned model ID
API_KEY = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"

# Initialize Mistral client
client = Mistral(api_key=API_KEY)

def get_mistral_response(query, retries=5):
    """Send query to Mistral's fine-tuned model and get the response with retry mechanism."""
    for attempt in range(retries):
        try:
            #print(f"[DEBUG] Sending query to Mistral fine-tuned model: {query}")
            # Use the correct method for sending messages to a fine-tuned model
            chat_response = client.chat.complete(
                model=FINE_TUNED_MODEL_ID,  # Fine-tuned model ID
                messages=[{"role": "user", "content": query}],
            )
            result = chat_response.choices[0].message.content
            #print(f"[DEBUG] Mistral response: {result}")  # Debug statement
            return result
        except Exception as e:
            print(f"[ERROR] An error occurred: {e}")  # Log the error message
            if hasattr(e, 'response') and e.response:  # If the exception has a response attribute
                print(f"[ERROR] Response: {e.response}")  # Print detailed error response
            if "429" in str(e):  # If the error is a rate limit (429)
                wait_time = 2 ** attempt + random.randint(1, 5)  # Exponential backoff with jitter
                print(f"[ERROR] Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)  # Wait before retrying
            else:
                return f"An error occurred: {e}"
    return "Failed to get a response after multiple retries."

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] No input provided. Please enter a query.")
        sys.exit(1)

    user_input = sys.argv[1]
    response = get_mistral_response(user_input)
    print(response)
