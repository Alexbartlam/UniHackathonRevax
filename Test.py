import requests
import json
import os

# Set your API key
RAGIE_API_KEY = "tnt_6NGf6ftD27M_AB98v0lafzGcunyMAjXMISoiE6NUTOi3j6LDm0daMzD"

def search_documents(query="Irish target", max_docs=2):
    """Search documents and return full pages from most relevant results"""
    url = "https://api.ragie.ai/retrievals"
    
    query_payload = {
        "query": query,
        "rerank": True,
    }

    print(f"\nSearching for: {query}")
    
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {RAGIE_API_KEY}",
            "Content-Type": "application/json"
        },
        data=json.dumps(query_payload)
    )
    
    results = response.json()
    
    # Process and format results
    formatted_results = []
    seen_files = set()
    
    if 'scored_chunks' in results:
        for chunk in results['scored_chunks']:
            doc_name = chunk.get('document_name', '')
            
            # Only process new documents
            if doc_name and doc_name not in seen_files:
                seen_files.add(doc_name)
                
                # Get all chunks for this document
                doc_chunks = [
                    c for c in results['scored_chunks'] 
                    if c.get('document_name') == doc_name
                ]
                
                # Sort chunks by score
                doc_chunks.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                # Format document result
                doc_result = {
                    'document_name': doc_name,
                    'best_match_score': doc_chunks[0].get('score', 0),
                    'pages': []
                }
                
                # Add unique pages with their full content
                seen_pages = set()
                for chunk in doc_chunks:
                    page_num = chunk.get('metadata', {}).get('page_number', 1)
                    if page_num not in seen_pages:
                        seen_pages.add(page_num)
                        doc_result['pages'].append({
                            'page_number': page_num,
                            'text': chunk.get('text', ''),
                            'score': chunk.get('score', 0)
                        })
                
                formatted_results.append(doc_result)
                
                # Break if we have enough documents
                if len(formatted_results) >= max_docs:
                    break
    
    # Print formatted results
    print("\nSearch Results:")
    print("=" * 80)
    for doc in formatted_results:
        print(f"\nDocument: {doc['document_name']}")
        print(f"Best Match Score: {doc['best_match_score']:.2%}")
        print("-" * 40)
        for page in doc['pages']:
            print(f"\nPage {page['page_number']} (Score: {page['score']:.2%})")
            print(f"Content: {page['text']}")
        print("=" * 80)
    
    return formatted_results

if __name__ == "__main__":
    # Test the search function
    results = search_documents()