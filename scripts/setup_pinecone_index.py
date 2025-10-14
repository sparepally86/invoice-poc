#!/usr/bin/env python3
"""
# scripts/setup_pinecone_index.py

This script fetches an example OpenAI embedding to determine the embedding dimension
and then creates a Pinecone index with that dimension if it doesn't exist.

Environment variables used (or replace inline):
- OPENAI_API_KEY
- PINECONE_API_KEY
- PINECONE_ENVIRONMENT (preferred) or PINECONE_ENV (legacy)
- PINECONE_INDEX_NAME (defaults to 'invoice-poc')
"""

import os
import openai
from pinecone import Pinecone, ServerlessSpec
import json

# Load .env if available (optional)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=os.environ.get("ENV_FILE", ".env"), override=False)
except Exception:
    pass

# Set these environment vars or replace below
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or "<REPLACE_WITH_OPENAI_KEY>"
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY") or "<REPLACE_WITH_PINECONE_KEY>"
# Prefer PINECONE_ENVIRONMENT but fall back to PINECONE_ENV for backward compatibility
PINECONE_ENV = os.environ.get("PINECONE_ENVIRONMENT") or os.environ.get("PINECONE_ENV") or "us-east-1-aws"
INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME") or "invoice-poc"

openai.api_key = OPENAI_API_KEY

# 1) get an example embedding to learn dimension
example_text = "sample embedding dimension check"
resp = openai.Embedding.create(input=example_text, model="text-embedding-3-small")
vec = resp["data"][0]["embedding"]
dim = len(vec)
print("Embedding dimension:", dim)

# 2) init pinecone and create index if not exists
pc = Pinecone(api_key=PINECONE_API_KEY)
existing_indexes = pc.list_indexes().names()

if INDEX_NAME not in existing_indexes:
    print("Creating Pinecone index:", INDEX_NAME)
    pc.create_index(
        name=INDEX_NAME,
        dimension=dim,
        metric="cosine",
        spec=ServerlessSpec(
            cloud='aws',
            region='us-east-1'
        )
    )
    print(f"Created index '{INDEX_NAME}' with dimension {dim}")
else:
    print("Index already exists:", INDEX_NAME)

print("Done. Index ready.")
