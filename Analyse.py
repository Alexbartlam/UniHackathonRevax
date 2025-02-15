import json
from mistralai import Mistral
import logging
import time
import random

logger = logging.getLogger(__name__)

def load_setup_data(file_path):
    """Load setup data from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_bullet_points(data, search_results=None, max_retries=5):
    """Generate bullet points from the setup data and search results using Mistral."""
    api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
    client = Mistral(api_key=api_key)

    # Create base prompt with setup data
    prompt = f"""You are going to be given information on a case the user is working on. 

Setup Information:
- Client Name: {data['client_name']}
- Client Location: {data['client_location']}
- Target Name: {data['target_name']}
- Target Location: {data['target_location']}

*** You MUST reply in this format *** Use the context of the submitted cases to understand how to populate this template.
*** Do not repeat the input information or slide data in your response. And do not provide any information after the response format.
*** COMPULSORY RESPONSE FORMAT ***:

- Establishing the aquisition structure:
  - A, B, C, D, ....

- Overview: 
  - (Text - Paragraph)
  
- Steps:
  - 1: (Text)
  - 2: (Text)
    ...
  - X: (Text)

Notes:
  - General: (Text)
  - Country A: (Text)
  - Country B: (Text)
    ...
  - Country X: (Text)

"""
    # Add search results if available, including the actual content
    if search_results and len(search_results) > 0:
        prompt += "\nRelevant Cases Found:\n"
        for result in search_results:
            prompt += f"\nFrom {result['file_name']} (Slide {result['slide_number']}, {result['similarity']*100:.1f}% match):\n"
            prompt += f"{result['text']}\n"
    
    prompt += "\nBased on the setup information, desired structure, and the relevant cases found, please generate the response"
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {max_retries}")
            response = client.chat.complete(
                model="mistral-medium",
                messages=[{"role": "user", "content": prompt}]
            )
            
            if response and response.choices and response.choices[0].message:
                return response.choices[0].message.content
            else:
                raise Exception("No response content received from Mistral")

        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:  # Rate limit error
                wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                logger.warning(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry...")
                time.sleep(wait_time)
                continue
            elif attempt == max_retries - 1:
                logger.error(f"Final attempt failed: {str(e)}")
                raise Exception(f"Analysis failed after {max_retries} attempts: {str(e)}")
            else:
                logger.error(f"Error in generate_bullet_points: {str(e)}")
                raise Exception(f"Analysis failed: {str(e)}")

    return "Error: Maximum retries exceeded"

if __name__ == "__main__":
    setup_data = load_setup_data('tests/debug_setup_data.json')
    bullet_points = generate_bullet_points(setup_data)
    print(bullet_points) 