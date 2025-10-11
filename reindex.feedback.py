#!/usr/bin/env python3
"""
scripts/reindex_feedback.py

Scan feedback collection, find explain text for feedback entries, and index them into the vector DB
using app.agents.retrieval.index_document().

NOTE: With the in-memory vector client, running this script as a separate process will NOT modify
the vector index inside your running webserver. To update the in-memory index used by the server,
use the dev HTTP trigger `app/api/dev_reindex_feedback.py` (also provided).

Usage:
  python scripts/reindex_feedback.py           # process all feedback (careful)
  python scripts/reindex_feedback.py --limit 50
  python scripts/reindex_feedback.py --dry-run
  python scripts/reindex_feedback.py --since 2025-10-01T00:00:00Z

"""

import argparse
from datetime import datetime
from typing import Optional
import sys
import os

# add project root to path so we can import app.* modules
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.storage.mongo_client import get_db
from app.agents.retrieval import index_document

def iso_to_dt(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def build_feedback_text(invoice: dict, explain_step: dict, feedback_doc: dict) -> str:
    """
    Construct a text blob to index for this feedback entry.
    Include: invoice id/ref, short invoice snippet, explanation text, and reviewer notes.
    """
    parts = []
    inv_ref = (invoice.get("header", {}) or {}).get("invoice_ref") or invoice.get("_id")
    parts.append(f"Invoice: {inv_ref}")

    # short invoice snippet (first line)
    lines = invoice.get("lines") or invoice.get("items") or []
    if isinstance(lines, list) and len(lines) > 0:
        first = lines[0]
        if isinstance(first, dict):
            parts.append(f"Line0: {first.get('description','')}")
        else:
            parts.append(f"Line0: {str(first)}")

    # explanation (if available)
    if explain_step and explain_step.get("result"):
        expl = explain_step.get("result", {}).get("explanation") or explain_step.get("result")
        parts.append(f"Explanation: {expl}")

    # feedback
    verdict = feedback_doc.get("verdict")
    notes = feedback_doc.get("notes", "")
    parts.append(f"Feedback verdict: {verdict}")
    if notes:
        parts.append(f"Feedback notes: {notes}")

    # include minimal metadata string
    parts.append(f"Feedback id: {feedback_doc.get('_id')}, user: {feedback_doc.get('user')}, created_at: {feedback_doc.get('created_at')}")

    return "\n".join([p for p in parts if p])

def find_explain_step_for_feedback(invoice: dict, step_id: Optional[str]) -> Optional[dict]:
    """
    Try to find the explain step referenced by step_id (timestamp) or return the latest ExplainAgent step.
    """
    steps = invoice.get("_workflow", {}).get("steps") or invoice.get("workflow", {}).get("steps") or []
    if not steps:
        return None
    # prefer explicit step_id match
    if step_id:
        for s in reversed(steps):
            if s.get("timestamp") == step_id or str(s.get("_id")) == str(step_id) or s.get("step_id") == step_id:
                return s
    # fallback: return latest ExplainAgent step
    for s in reversed(steps):
        if s.get("agent") == "ExplainAgent":
            return s
    return None

def reindex_feedback(limit: Optional[int] = None, since: Optional[str] = None, dry_run: bool = False):
    db = get_db()
    q = {}
    if since:
        dt = iso_to_dt(since)
        if dt:
            q["created_at"] = {"$gte": dt.isoformat().replace("+00:00", "Z")}
    cursor = db.feedback.find(q).sort("created_at", 1)
    count = 0
    total_chunks = 0
    for fb in cursor:
        if limit and count >= limit:
            break
        invoice_id = fb.get("invoice_id")
        if not invoice_id:
            print("Skipping feedback without invoice_id:", fb)
            continue
        invoice = db.invoices.find_one({"_id": invoice_id})
        if not invoice:
            print("Invoice not found for feedback:", fb.get("_id"))
            count += 1
            continue
        explain_step = find_explain_step_for_feedback(invoice, fb.get("step_id"))
        text_blob = build_feedback_text(invoice, explain_step, fb)
        doc_id = f"feedback::{fb.get('_id')}"
        meta = {
            "source": "feedback",
            "invoice_id": invoice_id,
            "feedback_id": str(fb.get("_id")),
            "verdict": fb.get("verdict"),
            "user": fb.get("user"),
            "created_at": fb.get("created_at")
        }
        print(f"Indexing feedback {fb.get('_id')} -> doc_id={doc_id} (dry_run={dry_run})")
        if not dry_run:
            chunks = index_document(doc_id, text_blob, metadata=meta)
            print(f"  -> created {len(chunks)} chunks")
            total_chunks += len(chunks)
        count += 1
    print(f"Processed {count} feedback entries. Total chunks indexed: {total_chunks}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max number of feedback docs to process")
    parser.add_argument("--since", type=str, default=None, help="Only process feedback created since ISO timestamp")
    parser.add_argument("--dry-run", action="store_true", help="Do not write into vector store; just print actions")
    args = parser.parse_args()
    reindex_feedback(limit=args.limit, since=args.since, dry_run=args.dry_run)
