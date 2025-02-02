import os
import time
import logging

logging.basicConfig(
    filename='/var/log/session_cleanup.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def cleanup_sessions():
    """Clean up old session files and log the action"""
    try:
        current_time = time.time()
        cleaned = 0
        
        for filename in os.listdir('/tmp'):
            if filename.startswith('conversation_state_'):
                filepath = os.path.join('/tmp', filename)
                if os.path.getmtime(filepath) < current_time - 3600:  # 1 hour
                    os.remove(filepath)
                    cleaned += 1
        
        logging.info(f"Cleaned up {cleaned} old session files")
    except Exception as e:
        logging.error(f"Cleanup error: {str(e)}")

if __name__ == '__main__':
    cleanup_sessions() 