# scripts/test_index_upsert.py
"""
Test script: Upsert and search a sample text via our PineconeClient (which uses OpenAI embeddings under the hood).
Run with the same environment variables you use on Render for a faithful test.
Required envs: OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME. For v2 SDK, also PINECONE_ENVIRONMENT.
"""
import os, time, json
from app.storage.pinecone_client import PineconeClient

def main():
    pc = PineconeClient()
    # Describe index stats if available
    try:
        print("Index info:", json.dumps(pc.describe_index(), indent=2, default=str))
    except Exception as e:
        print("describe_index failed:", e)

    doc_id = "doc-CHAIRS-EMB-001"
    text = "Invoice: chairs purchase. GST 18% applied. Delivery Mumbai."
    meta = {"type":"invoice","vendor":"Acme Corp","loc":"mumbai"}

    print("Upserting into Pinecone (will embed via OpenAI)...")
    res = pc.upsert(doc_id, text, metadata=meta)
    print("Upsert result:", res)

    time.sleep(1.5)
    print("Searching for similar with query 'chairs mumbai gst'...")
    hits = pc.search(query="chairs mumbai gst", k=3)
    print("Search hits:", json.dumps(hits, indent=2))

if __name__ == "__main__":
    main()
