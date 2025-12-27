#!/usr/bin/env python3
"""
Index historical invoices into the vector store for RAG retrieval.

This script:
1. Fetches successful invoices from MongoDB
2. Converts them to searchable text
3. Indexes them into the vector store (in-memory for POC)

Run this after backend startup to enable "Related cases" feature in ExplainAgent.

Usage:
    python scripts/index_historical_invoices.py
"""

import os
import json
import sys
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "invoice_poc")

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.retrieval import index_document
from app.storage.vector_client import get_vector_client


def invoice_to_text(invoice: dict) -> str:
    """Convert invoice to indexable text."""
    parts = []
    
    header = invoice.get("header", {}) or {}
    invoice_id = invoice.get("_id", "unknown")
    
    # Add invoice metadata
    parts.append(f"Invoice ID: {invoice_id}")
    parts.append(f"Vendor: {header.get('vendor_name', 'Unknown')}")
    parts.append(f"Amount: {header.get('amount', 0)}")
    parts.append(f"Currency: {header.get('currency', 'USD')}")
    
    if header.get("po_number"):
        parts.append(f"PO Number: {header.get('po_number')}")
    
    # Add line items
    lines = invoice.get("items") or invoice.get("lines") or []
    if lines:
        parts.append("Line Items:")
        for line in lines[:5]:  # Limit to first 5 lines
            item_text = line.get("item_text", "")
            amount = line.get("amount", 0)
            qty = line.get("quantity", 1)
            parts.append(f"  - {item_text} (Qty: {qty}, Amount: {amount})")
    
    # Add status
    parts.append(f"Status: {invoice.get('status', 'unknown')}")
    
    return "\n".join(parts)


def main():
    """Index historical invoices."""
    print("\n=== Indexing Historical Invoices for RAG ===\n")
    
    # Connect to MongoDB
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[MONGODB_DB]
        print(f"✓ Connected to MongoDB: {MONGODB_DB}")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        return False
    
    # Get vector client
    vc = get_vector_client()
    print(f"✓ Vector client initialized (in-memory)\n")
    
    # Fetch historical invoices with successful status
    successful_statuses = ["READY_FOR_POSTING", "CODED", "APPROVED", "POSTED"]
    query = {"status": {"$in": successful_statuses}}
    
    try:
        invoices = list(db.invoices.find(query).limit(20))  # Index up to 20 invoices
        print(f"Found {len(invoices)} historical invoices to index\n")
        
        if not invoices:
            print("No historical invoices found. Create some first and re-run.")
            return False
        
        indexed_count = 0
        for inv in invoices:
            invoice_id = inv.get("_id", "unknown")
            text = invoice_to_text(inv)
            
            # Index the invoice
            metadata = {
                "invoice_id": invoice_id,
                "status": inv.get("status"),
                "vendor": inv.get("header", {}).get("vendor_name"),
                "amount": inv.get("header", {}).get("amount"),
                "created_at": str(inv.get("created_at", "")),
                "source": "Past invoice"
            }
            
            try:
                index_document(invoice_id, text, metadata=metadata)
                indexed_count += 1
                print(f"  ✓ Indexed: {invoice_id} (Status: {inv.get('status')})")
            except Exception as e:
                print(f"  ✗ Failed to index {invoice_id}: {e}")
        
        print(f"\n=== Indexing Complete ===")
        print(f"Successfully indexed: {indexed_count}/{len(invoices)} invoices")
        print(f"RAG retrieval is now enabled for ExplainAgent\n")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during indexing: {e}")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
