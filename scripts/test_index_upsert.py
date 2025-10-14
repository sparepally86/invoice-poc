# scripts/test_index_upsert.py
"""
Test script: embed a sample text using app.ai.openai_client and upsert into Pinecone client.
Then search using the same embedding or a query embedding and print results.
Run with the same environment variables you use on Render for a faithful test.
"""
import os, time, json
from app.ai.openai_client import embed_text
from app.storage.pinecone_client import PineconeClient

def main():
    pc = PineconeClient()
    print("Indexes available (via client):", pc.list_indexes())

    doc_id = "doc-CHAIRS-EMB-001"
    text = "Invoice: chairs purchase. GST 18% applied. Delivery Mumbai."
    meta = {"type":"invoice","vendor":"Acme Corp","loc":"mumbai"}

    print("Embedding text via OpenAI...")
    emb = embed_text(text)
    print("Embedding length:", len(emb))

    print("Upserting into Pinecone with provided embedding...")
    res = pc.upsert(doc_id, text, metadata=meta, embedding=emb)
    print("Upsert result:", res)

    time.sleep(1.5)
    print("Searching for similar with query 'chairs mumbai gst'...")
    q_emb = embed_text("chairs mumbai gst")
    hits = pc.search(query="chairs mumbai gst", k=3)  # search computes its own embedding; alternative: extend search to accept vector
    print("Search hits:", json.dumps(hits, indent=2))

if __name__ == "__main__":
    main()
