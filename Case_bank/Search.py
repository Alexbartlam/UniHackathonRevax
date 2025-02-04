import os
import json
import sys
from pptx import Presentation
import numpy as np
from scipy.spatial.distance import cosine
from mistralai import Mistral
import time
import random

# Define search weight parameters
PERCENTAGE_FRONT = 0.7  # 70% weight for first page
PERCENTAGE_REST = 0.3   # 30% weight for rest of document
INTERNAL_PAGES_TO_RETURN = 3  # Number of most relevant pages to return per file

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

def find_most_relevant(query_embedding, embeddings, top_n=2):
    """Find the top N most relevant text chunks with weighted scoring."""
    if not query_embedding or not embeddings:
        return []
        
    similarities = []
    seen_slides = set()  # Track unique file+slide combinations
    
    for item in embeddings:
        # Create unique identifier for this slide
        slide_id = f"{item['file_name']}_{item['slide_number']}"
        
        # Skip if we've already seen this slide
        if slide_id in seen_slides:
            continue
            
        chunk_embedding = np.array(item["embedding"])
        base_similarity = 1 - cosine(query_embedding, chunk_embedding)
        
        # Apply weighting based on slide number
        if item["slide_number"] == 1:  # First page
            weighted_similarity = base_similarity * PERCENTAGE_FRONT
        else:  # Rest of document
            weighted_similarity = base_similarity * PERCENTAGE_REST
            
        similarities.append((item, weighted_similarity))
        seen_slides.add(slide_id)  # Mark this slide as seen
    
    # Sort by weighted similarity in descending order
    similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
    
    # Log the weighting effect
    log_debug(f"Search weights - First page: {PERCENTAGE_FRONT}, Rest: {PERCENTAGE_REST}")
    for item, similarity in similarities[:top_n]:
        log_debug(f"Match: {item['file_name']}, Slide: {item['slide_number']}, Score: {similarity:.3f}")
    
    return similarities[:top_n]

def deep_file_search(file_name, embeddings, query_embedding, prompt="Structure implementation steps and key considerations"):
    """Search within a specific file for the most relevant pages."""
    file_pages = []
    
    # Filter embeddings to only include pages from this file
    for item in embeddings:
        if item["file_name"] == file_name:
            chunk_embedding = np.array(item["embedding"])
            similarity = 1 - cosine(query_embedding, chunk_embedding)
            file_pages.append((item, similarity))
    
    # Sort by similarity (no weighting this time - we want pure relevance)
    file_pages.sort(key=lambda x: x[1], reverse=True)
    
    # Return top N most relevant pages
    return file_pages[:INTERNAL_PAGES_TO_RETURN]

def search(query_dict):
    """Two-stage search process."""
    try:
        # Stage 1: Initial file identification (existing weighted search)
        query_parts = []
        if query_dict.get('client'):
            query_parts.append(f"{query_dict['client']}")
            if query_dict.get('client_location'):
                query_parts.append(f"({query_dict['client_location']})")
        
        if query_dict.get('target'):
            query_parts.append(f"{query_dict['target']}")
            if query_dict.get('target_location'):
                query_parts.append(f"({query_dict['target_location']})")
                
        query = " Establishing the aquisition structure".join(query_parts)
        log_debug(f"Stage 1 - Processing initial query: {query}")
        
        # Get query embeddings for both stages
        initial_query_embedding = embed_query(query)
        deep_search_prompt = """- Establishing the aquisition structure:
                                - Bidco (Country), Midco (Country), Topco (Country)
                                Steps:
                                - 1: The firm does something
                                - 2: The firm does something else
                                - 3: The firm does something else
                                - 4: The firm does something else
                                - 5: The firm does something else

                                Notes:
                                - General: 
                                   - Some text
                                   - Some more text
                                   - Some more text
                                - Country A: 
                                   - Some text
                                   - Some more text
                                   - Some more text
                                - Country B: 
                                   - Some text
                                   - Some more text
                                   - Some more text
                                - Country X: 
                                   - Some text
                                   - Some more text
                                   - Some more text
                                """
        deep_query_embedding = embed_query(deep_search_prompt)
        
        if not initial_query_embedding or not deep_query_embedding:
            log_debug("Failed to generate query embeddings")
            return []
            
        # Load all embeddings
        embeddings = load_embeddings()
        if not embeddings:
            log_debug("No embeddings found")
            return []
            
        # Stage 1: Find most relevant files
        top_files = find_most_relevant(initial_query_embedding, embeddings)
        
        # Stage 2: Deep search within each identified file
        detailed_results = []
        for file_item, file_similarity in top_files:
            file_name = file_item["file_name"]
            log_debug(f"Stage 2 - Deep searching within file: {file_name}")
            
            # Find most relevant pages within this file
            relevant_pages = deep_file_search(file_name, embeddings, deep_query_embedding)
            
            # Log the results for debugging
            log_debug(f"Found {len(relevant_pages)} relevant pages in {file_name}")
            for page, sim in relevant_pages:
                log_debug(f"Page {page['slide_number']}: {sim:.3f}")
            
            # Format results for this file
            file_results = {
                "file_name": file_name,
                "overall_similarity": float(file_similarity),
                "pages": [{
                    "slide_number": page[0]["slide_number"],
                    "text": page[0]["text"],
                    "similarity": float(page[1])
                } for page in relevant_pages]
            }
            detailed_results.append(file_results)
            
            # Log the formatted results
            log_debug(f"Formatted results for {file_name}: {json.dumps(file_results, indent=2)}")
        
        log_debug(f"Completed two-stage search with {len(detailed_results)} files")
        return detailed_results

    except Exception as e:
        log_debug(f"Search error: {str(e)}")
        return []
