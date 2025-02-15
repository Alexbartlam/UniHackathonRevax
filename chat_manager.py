from mistralai import Mistral
import json
import logging
import time
import random

# Set up logging for this module
logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self):
        """
        Initialize a new chat manager instance.
        
        Attributes:
            api_key (str): Authentication key for Mistral AI API
            client: Instance of Mistral API client
            history (list): List of conversation messages, each a dict with 'role' and 'content'
            analysis_results: Stores the current case analysis
            search_results: Stores relevant similar cases found
            max_retries (int): Maximum attempts for API calls before giving up
        """
        # TODO: Move to environment variable for security
        self.api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
        
        # Initialize Mistral AI client for API interactions
        self.client = Mistral(api_key=self.api_key)
        
        # Initialize empty conversation history
        # Format: [{"role": "user"/"assistant", "content": "message"}, ...]
        self.history = []
        
        # Context holders - populated via set_context()
        self.analysis_results = None  # Holds current case analysis
        self.search_results = None    # Holds similar cases data
        
        # API retry configuration
        self.max_retries = 5  # Maximum retry attempts for failed API calls
        
        logger.debug("ChatManager initialized")

    def set_context(self, analysis_results=None, search_results=None):
        """
        Update the conversation context with new analysis and search results.
        Called when new case analysis is performed or search results are updated.

        Args:
            analysis_results: Structured analysis of the current case
            search_results: Collection of similar cases and their relevance

        Note: Both parameters are optional - can update either or both contexts
        """
        logger.debug(f"Setting context - Analysis exists: {bool(analysis_results)}, Search results exist: {bool(search_results)}")
        self.analysis_results = analysis_results
        self.search_results = search_results

    def process_message(self, user_input):
        """
        Process a user message and generate an AI response.
        
        This method:
        1. Validates required context exists
        2. Updates conversation history
        3. Constructs AI prompt with context and history
        4. Handles API communication with retry logic
        5. Processes and returns AI response
        
        Args:
            user_input (str): The user's message text

        Returns:
            dict: Response containing:
                - type: Message type identifier
                    * "system" for system messages
                    * "conversation" for normal chat
                    * "error" for error states
                - message: The response text
                - history: Current conversation history (for conversation type)
                
        Raises:
            Exception: Various exceptions possible from API communication
        """
        try:
            logger.debug(f"Processing message. Analysis exists: {bool(self.analysis_results)}")
            
            # Require analysis context before proceeding
            # This ensures the AI has necessary background to provide relevant answers
            if not self.analysis_results:
                logger.debug("No analysis results found - prompting user to fill form")
                return {
                    "type": "system",
                    "message": "Please fill in the input fields above and click submit first. This will help me provide more relevant assistance.",
                    "history": self.history
                }

            # Record user message in conversation history
            self.history.append({"role": "user", "content": user_input})
            logger.debug("Added user message to history")
            
            # Construct context message combining all available information
            # This helps the AI understand the full context of the conversation
            context = f"""Current Analysis Results:
{self.analysis_results}

Relevant Cases Found:
{json.dumps(self.search_results, indent=2) if self.search_results else 'No search results available'}

Use this context to provide informed responses to the user's questions.
"""
            # Prepare complete message array for AI
            # Include system prompts and recent conversation history
            messages = [
                # System messages define AI's role and provide context
                {"role": "system", "content": "You are a helpful M&A tax advisor assistant. Use the provided analysis and search results to give informed answers. Be concise and professional."},
                {"role": "system", "content": context}
            ] + self.history[-5:]  # Only include last 5 messages to manage context window

            # Implement retry logic with exponential backoff for API resilience
            for attempt in range(self.max_retries):
                try:
                    logger.debug(f"Attempt {attempt + 1} of {self.max_retries} to get Mistral response")
                    
                    # Make API call to Mistral
                    response = self.client.chat.complete(
                        model="mistral-medium",
                        messages=messages,
                        temperature=0.7,  # Higher values make output more creative/random
                        max_tokens=500    # Limit response length to prevent overlong replies
                    )
                    
                    # Extract AI's response and add to conversation history
                    ai_message = response.choices[0].message.content
                    self.history.append({"role": "assistant", "content": ai_message})
                    
                    # Return successful response with conversation type
                    return {
                        "type": "conversation",
                        "message": ai_message,
                        "history": self.history
                    }

                except Exception as e:
                    # Handle rate limiting with exponential backoff
                    if "429" in str(e) and attempt < self.max_retries - 1:  # Rate limit error
                        # Calculate wait time with exponential backoff and jitter
                        # Each retry waits longer: 1s, 2s, 4s, 8s, etc. plus random jitter
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    elif attempt == self.max_retries - 1:
                        # If final attempt fails, raise error
                        logger.error(f"Final attempt failed: {str(e)}")
                        raise Exception(f"Failed after {self.max_retries} attempts: {str(e)}")
                    else:
                        # For non-rate-limit errors, raise immediately
                        raise

        except Exception as e:
            # Log any errors and return error response
            logger.error(f"Error in chat processing: {str(e)}")
            return {
                "type": "error",
                "message": f"Error: {str(e)}"
            }

    def reset_conversation(self):
        """
        Reset the conversation history while maintaining the current context.
        
        This is useful when:
        - Starting a new conversation thread
        - Clearing out old context
        - Handling conversation errors
        
        Note: This only clears conversation history, not analysis or search results

        Returns:
            dict: System message confirming reset
        """
        logger.debug("Resetting conversation history")
        self.history = []  # Clear conversation history
        return {
            "type": "system",
            "message": "Conversation has been reset. Analysis and search results are still available."
        }