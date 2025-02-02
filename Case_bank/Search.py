import os
import json
import sys
from pptx import Presentation
import numpy as np
from scipy.spatial.distance import cosine
from mistralai import Mistral
import time
import random


# Debug: Log the Python executable being used
#print("Python executable:", sys.executable)
os.environ["MISTRAL_API_KEY"] = "9zMRdnt9VJz3fprSFW4ydGkKmC2sdYMF"

# Ensure the input query is coming from the command-line argument
if len(sys.argv) < 2:
    print("[ERROR] No query provided. Exiting...")
    sys.exit(1)

# Get the query from the command-line arguments
query = sys.argv[1]
#print(f"[DEBUG] Received query: {query}")  # Debug: Log the query received

# Mistral API Setup
api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    print("[ERROR] MISTRAL_API_KEY is not set. Exiting...")
    sys.exit(1)
model = "mistral-embed"
client = Mistral(api_key=api_key)

# Paths
base_dir = "/var/www/html/Case_bank"
processed_dir = os.path.join(base_dir, "Processed")

def extract_text_from_pptx(file_path):
    """Extract text from a .pptx file and return it as a list of chunks with metadata."""
    text_chunks = []
    presentation = Presentation(file_path)
    for slide_number, slide in enumerate(presentation.slides):
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip() != "":
                text_chunks.append({
                    "slide_number": slide_number + 1,
                    "text": shape.text.strip()
                })
    return text_chunks

def embed_query(query):
    """Generate embedding for the input query using Mistral with retries and exponential backoff."""
    retries = 5  # Number of retries
    for attempt in range(retries):
        try:
            #print(f"[DEBUG] Embedding query: {query}")  # Debug: Log the query before embedding
            response = client.embeddings.create(model=model, inputs=[query])
            #print(f"[DEBUG] Embedding response: {response}")  # Debug: Log the embedding response
            return response.data[0].embedding
        except Exception as e:
            if "429" in str(e):  # If rate limit error occurs
                wait_time = 2 ** attempt + random.randint(1, 5)  # Exponential backoff with jitter
                print(f"[ERROR] Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"[ERROR] Error embedding query: {e}")
                return None
    return None  # If retries are exhausted and still fails



def load_embeddings():
    """Load all embedded text chunks from the processed directory."""
    embeddings = []
    for file_name in os.listdir(processed_dir):
        if file_name.endswith(".json"):
            file_path = os.path.join(processed_dir, file_name)
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
                        else:
                            print(f"[DEBUG] Skipped an item due to missing keys: {item}")  # Debug: Log skipped items
    #print(f"[DEBUG] Loaded {len(embeddings)} embeddings.")  # Debug: Log number of embeddings loaded
    return embeddings

def find_most_relevant(query_embedding, embeddings, top_n=3):
    """Find the top N most relevant text chunks."""
    similarities = []
    for item in embeddings:
        chunk_embedding = np.array(item["embedding"])
        similarity = 1 - cosine(query_embedding, chunk_embedding)  # Cosine similarity
        similarities.append((item, similarity))
    
    # Sort by similarity in descending order
    similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
    #print(f"[DEBUG] Found {len(similarities)} similarities.")  # Debug: Log number of similarities found
    return similarities[:top_n]

def main():
    # Ensure the query is passed and received
    #print(f"[DEBUG] Query received: {query}")
    
    query_embedding = embed_query(query)
    if query_embedding:
        embeddings = load_embeddings()
        if embeddings:
            # Find the top matches without including the embeddings
            top_matches = find_most_relevant(query_embedding, embeddings)

            # Only return the relevant metadata, not the embeddings themselves
            print("\nTop 3 Relevant Results: \n")
            for i, (item, similarity) in enumerate(top_matches, start=1):
                # Log the relevant data: file name, slide number, and text
                print(f"{i}. Similarity: {similarity:.2f}")
                print(f"   File: {item['file_name']}, Slide: {item['slide_number']}")
                print(f"   Text: {item['text']}")
                print("-" * 50)

            # You can return this data to the frontend or API as needed
            # For example, returning only the metadata as a string or a JSON object
            return [{"file_name": item['file_name'], 
                     "slide_number": item['slide_number'],
                     "text": item['text'],
                     "similarity": similarity} for item, similarity in top_matches]
        else:
            print("No embeddings found.")
    else:
        print("Failed to generate query embedding.")

if __name__ == "__main__":
    main()
