#!/usr/bin/env python3
"""
# scripts/setup_pinecone_index.py

This script fetches an example OpenAI embedding to determine the embedding dimension
and then creates a Pinecone index with that dimension if it doesn't exist.

Environment variables used (or replace inline):
- OPENAI_API_KEY
- PINECONE_API_KEY
- PINECONE_ENV
- PINECONE_INDEX_NAME (defaults to 'invoice-poc')
"""

import os
import openai
import pinecone
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
PINECONE_ENV = os.environ.get("PINECONE_ENV") or "<REPLACE_WITH_PINECONE_ENV>"
INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME") or "invoice-poc"

openai.api_key = OPENAI_API_KEY

# 1) get an example embedding to learn dimension
example_text = "sample embedding dimension check"
resp = openai.Embedding.create(input=example_text, model="text-embedding-3-small")
vec = resp["data"][0]["embedding"]
dim = len(vec)
print("Embedding dimension:", dim)

# 2) init pinecone and create index if not exists
pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
if INDEX_NAME not in pinecone.list_indexes():
    print("Creating Pinecone index:", INDEX_NAME)
    pinecone.create_index(INDEX_NAME, dimension=dim, metric="cosine")
else:
    print("Index already exists:", INDEX_NAME)

print("Done. Index ready.")
