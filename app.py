from flask import Flask, request, session, jsonify, render_template, url_for
import json
import os
import time
from process_message import process_message
from datetime import timedelta
import random
import uuid

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your-secret-key-here'  # Replace with secure key
app.permanent_session_lifetime = timedelta(hours=1)

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

        # Check if this is a new session or greeting
        if 'session_id' not in session or user_message.lower() in ['hi', 'hello', 'hey']:
            # Generate new session ID
            session['session_id'] = str(uuid.uuid4())
            # Clean up any existing state file
            state_file = f"/tmp/conversation_state_{session['session_id']}.json"
            if os.path.exists(state_file):
                os.remove(state_file)

        # Process the message
        response = process_message(session['session_id'], user_message)
        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}")
        return jsonify({
            "type": "error",
            "message": f"ERROR: {str(e)}",
            "progress": 0
        })

@app.route('/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation state"""
    try:
        if 'session_id' in session:
            state_file = f"/tmp/conversation_state_{session['session_id']}.json"
            if os.path.exists(state_file):
                os.remove(state_file)
        session.clear()
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error(f"Reset error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Ensure tmp directory exists
    os.makedirs('/tmp', exist_ok=True)
    app.run(debug=True) 