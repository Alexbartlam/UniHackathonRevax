from flask import Flask, request, session, jsonify, render_template, url_for
from datetime import timedelta
import json
import os
import time
import random
import uuid
import logging
from Case_bank.Search import search
from Analyse import generate_bullet_points
import asyncio
from concurrent.futures import ThreadPoolExecutor
from chat_manager import ChatManager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your-secret-key-here'  # Replace with secure key
app.permanent_session_lifetime = timedelta(hours=1)

# Store chat managers for each session
chat_managers = {}

def cleanup_old_sessions():
    """Clean up session files older than 1 hour"""
    try:
        current_time = time.time()
        for filename in os.listdir('/tmp'):
            if filename.startswith('conversation_state_'):
                filepath = os.path.join('/tmp', filename)
                if os.path.getmtime(filepath) < current_time - 3600:  # 1 hour
                    os.remove(filepath)
    except Exception as e:
        app.logger.error(f"Session cleanup error: {str(e)}")

@app.before_request
def before_request():
    """Run before each request"""
    # Make sessions permanent but with timeout
    session.permanent = True
    # Clean up old session files periodically
    if random.random() < 0.1:  # 10% chance to run cleanup
        cleanup_old_sessions()

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id')
        
        logger.debug(f"Chat request received - Session ID: {session_id}, Message: {user_message}")

        if not session_id:
            session_id = str(uuid.uuid4())
            logger.debug(f"Created new session ID: {session_id}")
        
        # Get or create chat manager for this session
        if session_id not in chat_managers:
            logger.debug(f"Creating new chat manager for session {session_id}")
            chat_managers[session_id] = ChatManager()
            # Set context from session if available
            if 'analysis_results' in session and 'search_results' in session:
                logger.debug("Setting context from session")
                chat_managers[session_id].set_context(
                    session.get('analysis_results'),
                    session.get('search_results')
                )
        
        # Process the message
        chat_manager = chat_managers[session_id]
        logger.debug(f"Chat manager has analysis: {bool(chat_manager.analysis_results)}")
        response = chat_manager.process_message(user_message)
        response['session_id'] = session_id
        
        return jsonify(response)

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({
            "type": "error",
            "message": f"Error: {str(e)}",
            "session_id": session_id
        })

@app.route('/reset-chat', methods=['POST'])
def reset_chat():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if session_id in chat_managers:
            response = chat_managers[session_id].reset_conversation()
            response['session_id'] = session_id
            return jsonify(response)
        
        return jsonify({
            "type": "error",
            "message": "Session not found",
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Reset chat error: {str(e)}")
        return jsonify({
            "type": "error",
            "message": f"Error: {str(e)}"
        })

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/')
def home():
    logger.debug("Home route accessed")
    return render_template('index.html')

@app.route('/setup')
def setup():
    logger.debug("Setup route accessed")
    return render_template('setup.html')

@app.route('/store-setup', methods=['POST'])
def store_setup():
    try:
        setup_data = request.get_json()
        logger.info(f"Received setup data: {setup_data}")
        
        # Create search_data with correct field names
        search_data = {
            'client': setup_data.get('client_name', ''),
            'client_location': setup_data.get('client_location', ''),
            'target': setup_data.get('target_name', ''),
            'target_location': setup_data.get('target_location', '')
        }

        # Get search results only
        search_results = search(search_data)
        
        response = {
            "status": "success",
            "message": "Setup data processed successfully",
            "search_results": search_results
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in store_setup: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        setup_data = data.get('setup_data')
        search_results = data.get('search_results')
        
        # Format search results for analysis
        formatted_results = []
        for file_result in search_results:
            for page in file_result['pages']:
                formatted_results.append({
                    "file_name": file_result['file_name'],
                    "slide_number": page['slide_number'],
                    "text": page['text'],
                    "similarity": page['similarity']
                })
        
        # Generate analysis with formatted results
        analysis_results = generate_bullet_points(setup_data, formatted_results)
        
        return jsonify({
            "status": "success",
            "analysis_results": analysis_results
        })
        
    except Exception as e:
        logger.error(f"Error in analyze: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

if __name__ == '__main__':
    # Ensure tmp directory exists
    os.makedirs('/tmp', exist_ok=True)
    logger.info("Starting Flask application")
    app.run(debug=True) 