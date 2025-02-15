from flask import Flask, request, session, jsonify, render_template, url_for, redirect
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
import fitz
from io import BytesIO
import base64
from mistralai import Mistral  # Add this import at the top
from functools import wraps

# Configure logging
logging.basicConfig(
    filename='/var/log/revax/flask.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.urandom(24)  # Required for session management
app.permanent_session_lifetime = timedelta(hours=1)
app.config['PASSWORD'] = 'Revax@2025'  # Change this to your desired password

# Store chat managers for each session
chat_managers = {}

def cleanup_old_sessions():
    """
    Clean up session files older than 1 hour to prevent storage bloat.
    
    This function:
    1. Scans the /tmp directory for conversation state files
    2. Checks modification time of each file
    3. Removes files older than 1 hour
    4. Logs any errors encountered during cleanup
    """
    try:
        current_time = time.time()
        for filename in os.listdir('/tmp'):
            if filename.startswith('conversation_state_'):
                filepath = os.path.join('/tmp', filename)
                # Remove files older than 1 hour (3600 seconds)
                if os.path.getmtime(filepath) < current_time - 3600:
                    os.remove(filepath)
    except Exception as e:
        app.logger.error(f"Session cleanup error: {str(e)}")

@app.before_request
def before_request():
    """
    Middleware that runs before each request is processed.
    
    Performs:
    1. Sets session as permanent with configured timeout
    2. Randomly triggers old session cleanup (10% chance per request)
    """
    session.permanent = True  # Enable session timeout
    if random.random() < 0.1:  # 10% chance to run cleanup
        cleanup_old_sessions()

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle chat interactions between user and AI.
    
    Process:
    1. Extracts message and session ID from request
    2. Creates or retrieves chat manager for session
    3. Sets context if available in session
    4. Processes message and returns AI response
    
    Returns:
        JSON response containing:
        - AI message
        - Session ID
        - Error information (if applicable)
    """
    try:
        # Extract data from request
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id')
        
        logger.debug(f"Chat request received - Session ID: {session_id}, Message: {user_message}")

        # Generate new session ID if none provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.debug(f"Created new session ID: {session_id}")
        
        # Initialize or retrieve chat manager for session
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
        
        # Process message and return response
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
    """
    Reset a chat session while maintaining context.
    
    Process:
    1. Gets session ID from request
    2. Finds corresponding chat manager
    3. Resets conversation history
    4. Returns confirmation or error message
    """
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
    """
    Basic health check endpoint for monitoring.
    Returns simple status message to confirm application is running.
    """
    return jsonify({"status": "healthy"})

# Define login_required decorator BEFORE any routes that use it
def login_required(f):
    """
    Decorator to protect routes that require authentication.
    
    Functionality:
    1. Checks if user is logged in via session
    2. Redirects to login page if not authenticated
    3. Allows access to route if authenticated
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.
    
    GET: Display login form
    POST: Process login attempt
    - Validates password
    - Sets session if successful
    - Shows error if invalid
    """
    if request.method == 'POST':
        if request.form['password'] == app.config['PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Handle user logout.
    Removes session data and redirects to login page.
    """
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Protected routes
@app.route('/')
@login_required
def home():
    """Main application page, requires authentication."""
    logger.debug("Home route accessed")
    return render_template('index.html')

@app.route('/setup')
@login_required
def setup():
    """Setup page for configuring case analysis, requires authentication."""
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

@app.route('/get_pdf_page/<path:pdf_path>/<int:page_number>')
def get_pdf_page(pdf_path, page_number):
    try:
        # Debug prints
        print("\nPDF Preview Request:")
        print(f"Raw PDF path: {pdf_path}")
        print(f"Page number: {page_number}")
        
        # Clean the filename and ensure it's just the filename, not a path
        pdf_path = os.path.basename(pdf_path.replace('%20', ' '))
        print(f"Cleaned PDF path: {pdf_path}")
        
        # List contents of target directory
        target_dir = '/var/www/html/Case_bank/Target'
        print(f"\nContents of {target_dir}:")
        try:
            for f in os.listdir(target_dir):
                print(f"- {f}")
        except Exception as e:
            print(f"Error listing directory: {str(e)}")
        
        # Use the same base directory as Search.py
        full_path = os.path.join('/var/www/html/Case_bank/Target', pdf_path)
        print(f"Attempting to access: {full_path}")
        
        # Check file existence
        if not os.path.exists(full_path):
            print(f"File not found at: {full_path}")
            return jsonify({'error': f'PDF file not found at {full_path}'}), 404
            
        # Check file permissions
        try:
            with open(full_path, 'rb') as f:
                pass
            print("File is readable")
        except Exception as e:
            print(f"Permission error: {str(e)}")
            return jsonify({'error': f'Permission denied: {str(e)}'}), 500
        
        # Try to open PDF
        try:
            doc = fitz.open(full_path)
            page = doc[page_number]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # Save to a temporary file first
            temp_path = "/tmp/temp_preview.png"
            pix.save(temp_path)
            
            # Read the temporary file
            with open(temp_path, 'rb') as f:
                img_data = f.read()
            
            # Clean up
            os.remove(temp_path)
            
            # Convert to base64
            img_base64 = base64.b64encode(img_data).decode()
            return jsonify({'image': img_base64})
            
        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/refine-analysis', methods=['POST'])
def refine_analysis():
    try:
        data = request.json
        
        # Initialize Mistral client
        api_key = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"
        client = Mistral(api_key=api_key)
        
        # Create the prompt
        prompt = f"""You are going to refine an existing analysis based on the user's request.

Current Setup Information:
{json.dumps(data['setup_data'], indent=2)}

Search Results:
{json.dumps(data['search_results'], indent=2)}

Current Analysis:
{data['current_analysis']}

User's Refinement Request:
{data['refinement_request']}

*** You MUST reply in this format *** Use the context of the submitted cases to understand how to populate this template.
*** Do not repeat the input information or slide data in your response. And do not provide any information after the response format.
*** COMPULSORY RESPONSE FORMAT ***:

- Establishing the aquisition structure:
  - A, B, C, D, ....
Steps:
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
        
        # Get response from Mistral
        response = client.chat.complete(
            model="mistral-medium",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        refined_analysis = response.choices[0].message.content
        
        return jsonify({
            'analysis_results': refined_analysis
        })
        
    except Exception as e:
        logger.error(f"Error in refine_analysis: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

if __name__ == '__main__':
    # Ensure tmp directory exists
    os.makedirs('/tmp', exist_ok=True)
    logger.info("Starting Flask application")
    app.run(debug=True) 