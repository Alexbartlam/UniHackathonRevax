import os
import json
import sys
from pptx import Presentation
import numpy as np
from scipy.spatial.distance import cosine
from mistralai import Mistral
import time
import random

def log_debug(message):
    try:
        with open('/tmp/search_debug.log', 'a') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {str(message)}\n")
    except Exception as e:
        print(f"Failed to write to debug log: {str(e)}")

def embed_query(query):
    """Generate embedding for the input query using Mistral with retries and exponential backoff."""
    client = Mistral(api_key="9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF")
    retries = 5  # Number of retries
    for attempt in range(retries):
        try:
            log_debug(f"Embedding query: {query}")
            response = client.embeddings.create(model="mistral-embed", inputs=[query])
            return response.data[0].embedding
        except Exception as e:
            if "429" in str(e):  # If rate limit error occurs
                wait_time = 2 ** attempt + random.randint(1, 5)  # Exponential backoff with jitter
                log_debug(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                log_debug(f"Error embedding query: {e}")
                return None
    return None

def load_embeddings():
    """Load all embedded text chunks from the processed directory."""
    base_dir = "/var/www/html/Case_bank"
    processed_dir = os.path.join(base_dir, "Processed")
    embeddings = []
    
    for file_name in os.listdir(processed_dir):
        if file_name.endswith(".json"):
            file_path = os.path.join(processed_dir, file_name)
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    if "embedded_text" in data:
                        for item in data["embedded_text"]:
                            if "text" in item and "embedding" in item:
                                embeddings.append({
                                    "file_name": data["file_name"],
                                    "slide_number": item["slide_number"],
                                    "text": item["text"],
                                    "embedding": item["embedding"]
                                })
            except Exception as e:
                log_debug(f"Error loading {file_name}: {str(e)}")
    
    log_debug(f"Loaded {len(embeddings)} embeddings")
    return embeddings

def find_most_relevant(query_embedding, embeddings, top_n=3):
    """Find the top N most relevant text chunks."""
    if not query_embedding or not embeddings:
        return []
        
    similarities = []
    for item in embeddings:
        chunk_embedding = np.array(item["embedding"])
        similarity = 1 - cosine(query_embedding, chunk_embedding)
        similarities.append((item, similarity))
    
    # Sort by similarity in descending order
    similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
    return similarities[:top_n]

def search(query_dict):
    """Main search function that coordinates the embedding and matching process."""
    try:
        # Construct search query with all available information
        query_parts = []
        if query_dict.get('client'):
            query_parts.append(f"{query_dict['client']}")
            if query_dict.get('client_location'):
                query_parts.append(f"({query_dict['client_location']})")
        
        if query_dict.get('target'):
            query_parts.append(f"{query_dict['target']}")
            if query_dict.get('target_location'):
                query_parts.append(f"({query_dict['target_location']})")
                
        if query_dict.get('transaction_type'):
            query_parts.append(query_dict['transaction_type'])
            
        query = " ".join(query_parts)
        log_debug(f"Processing query: {query}")
        
        # Get query embedding
        query_embedding = embed_query(query)
        if not query_embedding:
            log_debug("Failed to generate query embedding")
            return []
            
        # Load document embeddings
        embeddings = load_embeddings()
        if not embeddings:
            log_debug("No embeddings found")
            return []
            
        # Find matches
        top_matches = find_most_relevant(query_embedding, embeddings)
        
        # Format results
        results = []
        for item, similarity in top_matches:
            results.append({
                "file_name": item["file_name"],
                "slide_number": item["slide_number"],
                "text": item["text"],
                "similarity": float(similarity)  # Convert numpy float to Python float
            })
            
        log_debug(f"Found {len(results)} relevant matches")
        return results

    except Exception as e:
        log_debug(f"Search error: {str(e)}")
        return []
