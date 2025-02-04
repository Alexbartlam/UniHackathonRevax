import json
from mistralai import Mistral
import logging

logger = logging.getLogger(__name__)

def load_setup_data(file_path):
    """Load setup data from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_bullet_points(data, search_results=None):
    """Generate bullet points from the setup data and search results using Mistral."""
    try:
        api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
        client = Mistral(api_key=api_key)

        # Create base prompt with setup data
        prompt = f"""Please summarize the following information in bullet points:

Setup Information:
- Client Name: {data['client_name']}
- Client Location: {data['client_location']}
- Target Name: {data['target_name']}
- Target Location: {data['target_location']}
- Lead Partner: {data['lead_partner']}

"""
        # Add search results if available
        if search_results and len(search_results) > 0:
            prompt += "\nRelevant Cases Found:\n"
            for result in search_results:
                prompt += f"- {result['file_name']} (Slide {result['slide_number']}, {result['similarity']*100:.1f}% match)\n"
        
        prompt += "\nPlease provide a comprehensive analysis in bullet points, incorporating both the setup information and any relevant cases found."
        
        logger.debug(f"Sending prompt to Mistral: {prompt}")
        
        response = client.chat.complete(
            model="mistral-medium",
            messages=[{"role": "user", "content": prompt}]
        )
        
        logger.debug(f"Received response from Mistral: {response}")
        
        if response and response.choices and response.choices[0].message:
            return response.choices[0].message.content
        else:
            return "Error: No response content received from Mistral"

    except Exception as e:
        logger.error(f"Error in generate_bullet_points: {str(e)}")
        raise Exception(f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    setup_data = load_setup_data('html/debug_setup_data.json')
    bullet_points = generate_bullet_points(setup_data)
    print(bullet_points) 