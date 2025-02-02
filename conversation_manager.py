from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from mistralai import Mistral
import json
import os

class ConversationManager:
    def __init__(self):
        self.api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
        self.client = Mistral(api_key=self.api_key)
        self.memory = ConversationBufferMemory()
        self.conversation_state = "gathering_info"  # States: gathering_info, searching_docs, refining
        self.required_info = {
            "client_name": None,
            "client_location": None,
            "target_name": None,
            "target_location": None,
            "leading_partner": None
        }
        
        # Custom prompt for information gathering
        self.info_gathering_prompt = PromptTemplate(
            input_variables=["history", "input"],
            template="""You are a helpful assistant gathering information about a user's query.
            Previous conversation: {history}
            User: {input}
            Assistant: Let's make sure I understand your needs correctly."""
        )
        
        self.chain = ConversationChain(
            prompt=self.info_gathering_prompt,
            memory=self.memory
        )

    def has_sufficient_info(self):
        """Check if we have gathered enough information to proceed with search"""
        return all(value is not None for value in self.required_info.values())

    def process_message(self, user_input):
        if self.conversation_state == "gathering_info":
            # Update required info based on user input
            self._update_required_info(user_input)
            
            if self.has_sufficient_info():
                self.conversation_state = "searching_docs"
                return self._perform_rag_search()
            else:
                return self._get_next_question()
                
        elif self.conversation_state == "searching_docs":
            return self._process_search_refinement(user_input)
            
        elif self.conversation_state == "refining":
            return self._process_refinement(user_input)

    def _update_required_info(self, user_input):
        # Use Mistral to analyze user input and update required_info
        analysis_prompt = f"""Analyze this user input and extract:
        1. Main topic
        2. Specific requirements
        
        User input: {user_input}"""
        
        response = self._get_mistral_response(analysis_prompt)
        # Parse response and update required_info
        # This is a simplified version - you'd want more robust parsing
        if "topic:" in response.lower():
            self.required_info["topic"] = response.split("topic:")[1].split("\n")[0].strip()
        if "requirements:" in response.lower():
            self.required_info["specific_requirements"] = response.split("requirements:")[1].strip()

    def _get_next_question(self):
        if not self.required_info["topic"]:
            return "Could you tell me more specifically what topic you're interested in?"
        elif not self.required_info["specific_requirements"]:
            return "What specific aspects or requirements are you looking for regarding this topic?"
        return None

    def _perform_rag_search(self):
        # Use your existing Search.py functionality here
        search_query = f"{self.required_info['topic']} {self.required_info['specific_requirements']}"
        # Import and use your existing search functionality
        from Case_bank.Search import main as search_main
        results = search_main(search_query)
        
        self.conversation_state = "refining"
        return {
            "type": "search_results",
            "results": results,
            "message": "I found these relevant documents. Would you like me to explain any specific aspect in more detail?"
        }

    def _process_refinement(self, user_input):
        # Handle user's refinement requests
        refinement_prompt = f"""Based on the previous search results and this user request,
        provide a detailed response:
        User request: {user_input}"""
        
        return self._get_mistral_response(refinement_prompt)

    def _get_mistral_response(self, prompt):
        response = self.client.chat.complete(
            model="mistral-medium",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content 