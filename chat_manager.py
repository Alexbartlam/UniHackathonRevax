from mistralai import Mistral
import json
import logging

logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self):
        self.api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
        self.client = Mistral(api_key=self.api_key)
        self.history = []
        self.analysis_results = None
        self.search_results = None

    def set_context(self, analysis_results=None, search_results=None):
        """Update the context with current analysis and search results"""
        self.analysis_results = analysis_results
        self.search_results = search_results

    def process_message(self, user_input):
        """Process a message from the user and return a response"""
        try:
            # Check if analysis has been performed
            if not self.analysis_results:
                return {
                    "type": "conversation",
                    "message": "Please fill in the input fields above and click submit first. This will help me provide more relevant assistance.",
                    "history": self.history
                }

            # Add user message to history
            self.history.append({"role": "user", "content": user_input})
            
            # Create the context-aware prompt
            context = f"""Current Analysis Results:
{self.analysis_results}

Relevant Cases Found:
{json.dumps(self.search_results, indent=2) if self.search_results else 'No search results available'}

Use this context to provide informed responses to the user's questions.
"""

            # Create messages array with system context and history
            messages = [
                {"role": "system", "content": "You are a helpful M&A tax advisor assistant. Use the provided analysis and search results to give informed answers. Be concise and professional."},
                {"role": "system", "content": context}
            ] + self.history[-5:]  # Include last 5 messages for context
            
            # Get response from Mistral
            response = self.client.chat.complete(
                model="mistral-medium",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            # Extract the response content
            ai_message = response.choices[0].message.content
            
            # Add AI response to history
            self.history.append({"role": "assistant", "content": ai_message})
            
            return {
                "type": "conversation",
                "message": ai_message,
                "history": self.history
            }

        except Exception as e:
            logger.error(f"Error in chat processing: {str(e)}")
            return {
                "type": "error",
                "message": f"Error: {str(e)}"
            }

    def reset_conversation(self):
        """Reset the conversation history"""
        self.history = []
        return {
            "type": "system",
            "message": "Conversation has been reset."
        } 