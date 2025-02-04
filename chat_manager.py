from mistralai import Mistral
import json
import logging
import time
import random

logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self):
        self.api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
        self.client = Mistral(api_key=self.api_key)
        self.history = []
        self.analysis_results = None
        self.search_results = None
        self.max_retries = 5
        logger.debug("ChatManager initialized")

    def set_context(self, analysis_results=None, search_results=None):
        """Update the context with current analysis and search results"""
        logger.debug(f"Setting context - Analysis exists: {bool(analysis_results)}, Search results exist: {bool(search_results)}")
        self.analysis_results = analysis_results
        self.search_results = search_results

    def process_message(self, user_input):
        """Process a message from the user and return a response"""
        try:
            logger.debug(f"Processing message. Analysis exists: {bool(self.analysis_results)}")
            
            if not self.analysis_results:
                logger.debug("No analysis results found - prompting user to fill form")
                return {
                    "type": "system",
                    "message": "Please fill in the input fields above and click submit first. This will help me provide more relevant assistance.",
                    "history": self.history
                }

            self.history.append({"role": "user", "content": user_input})
            logger.debug("Added user message to history")
            
            context = f"""Current Analysis Results:
{self.analysis_results}

Relevant Cases Found:
{json.dumps(self.search_results, indent=2) if self.search_results else 'No search results available'}

Use this context to provide informed responses to the user's questions.
"""
            messages = [
                {"role": "system", "content": "You are a helpful M&A tax advisor assistant. Use the provided analysis and search results to give informed answers. Be concise and professional."},
                {"role": "system", "content": context}
            ] + self.history[-5:]

            # Retry logic with exponential backoff
            for attempt in range(self.max_retries):
                try:
                    logger.debug(f"Attempt {attempt + 1} of {self.max_retries} to get Mistral response")
                    response = self.client.chat.complete(
                        model="mistral-medium",
                        messages=messages,
                        temperature=0.7,
                        max_tokens=500
                    )
                    
                    ai_message = response.choices[0].message.content
                    self.history.append({"role": "assistant", "content": ai_message})
                    
                    return {
                        "type": "conversation",
                        "message": ai_message,
                        "history": self.history
                    }

                except Exception as e:
                    if "429" in str(e) and attempt < self.max_retries - 1:  # Rate limit error
                        wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                        logger.warning(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    elif attempt == self.max_retries - 1:
                        logger.error(f"Final attempt failed: {str(e)}")
                        raise Exception(f"Failed after {self.max_retries} attempts: {str(e)}")
                    else:
                        raise

        except Exception as e:
            logger.error(f"Error in chat processing: {str(e)}")
            return {
                "type": "error",
                "message": f"Error: {str(e)}"
            }

    def reset_conversation(self):
        """Reset the conversation history but maintain context"""
        logger.debug("Resetting conversation history")
        self.history = []
        return {
            "type": "system",
            "message": "Conversation has been reset. Analysis and search results are still available."
        }