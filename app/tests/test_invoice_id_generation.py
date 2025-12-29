"""
Test suite for sequential invoice_id generation.

Verifies:
1. get_next_invoice_id() returns monotonically increasing integers
2. Concurrent calls generate distinct, non-colliding IDs
3. Counter initialization (upsert) is idempotent
4. Invoice documents store invoice_id immutably

NOTE: These tests require MONGODB_URI to be set in the environment.
To run: pytest app/tests/test_invoice_id_generation.py -v

Example:
  export MONGODB_URI=mongodb+srv://...
  pytest app/tests/test_invoice_id_generation.py -v
"""

import asyncio
import os
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

# Skip all tests if MONGODB_URI is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("MONGODB_URI"),
    reason="MONGODB_URI not set - skipping MongoDB integration tests"
)

from app.storage.mongo_client import get_db, get_next_invoice_id


class TestSequentialInvoiceIdGeneration:
    """Test sequential invoice_id generation under various conditions."""

    def setup_method(self):
        """Reset counters collection before each test."""
        db = get_db()
        db.counters.delete_one({"_id": "invoice"})

    def test_get_next_invoice_id_starts_from_one(self):
        """Test that the first call returns 1."""
        id1 = get_next_invoice_id()
        assert id1 == 1

    def test_get_next_invoice_id_increments_sequentially(self):
        """Test that successive calls increment by 1."""
        ids = [get_next_invoice_id() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]

    def test_concurrent_invoice_id_generation_no_collisions(self):
        """Test that concurrent calls generate distinct, sequential IDs."""
        num_threads = 10
        ids = []

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(get_next_invoice_id)
                for _ in range(num_threads)
            ]
            ids = [f.result() for f in as_completed(futures)]

        # All IDs should be unique
        assert len(set(ids)) == num_threads, f"Duplicate IDs detected: {ids}"

        # All IDs should be in range [1, num_threads]
        assert set(ids) == set(range(1, num_threads + 1)), \
            f"IDs not in expected range: {sorted(ids)}"

    def test_concurrent_invoice_id_generation_large_batch(self):
        """Test with larger batch of concurrent requests (stress test)."""
        num_threads = 50
        ids = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(get_next_invoice_id)
                for _ in range(num_threads)
            ]
            ids = [f.result() for f in as_completed(futures)]

        # Verify all IDs are unique and sequential
        assert len(set(ids)) == num_threads
        assert max(ids) == num_threads
        assert min(ids) == 1

    def test_counter_initialization_is_idempotent(self):
        """Test that counter can be initialized safely multiple times."""
        # First initialization
        id1 = get_next_invoice_id()
        assert id1 == 1

        # Verify counter doc exists
        db = get_db()
        counter_doc = db.counters.find_one({"_id": "invoice"})
        assert counter_doc is not None
        assert counter_doc["seq"] == 1

        # Second ID should be 2, not reset
        id2 = get_next_invoice_id()
        assert id2 == 2

    def test_invoice_id_is_numeric_and_human_readable(self):
        """Test that invoice_id is a plain integer (human-readable)."""
        invoice_id = get_next_invoice_id()
        assert isinstance(invoice_id, int)
        assert invoice_id > 0  # Positive integers only

    def test_invoice_id_stored_in_document(self):
        """Test that invoice_id is stored in the invoice document."""
        db = get_db()
        
        # Clear invoices and counters
        db.invoices.delete_many({})
        db.counters.delete_one({"_id": "invoice"})
        
        # Create an invoice
        invoice_id = get_next_invoice_id()
        invoice_doc = {
            "_id": invoice_id,
            "invoice_id": invoice_id,
            "status": "RECEIVED",
            "header": {},
            "created_at": "2024-01-01T00:00:00Z"
        }
        db.invoices.insert_one(invoice_doc)
        
        # Fetch and verify
        doc = db.invoices.find_one({"_id": invoice_id})
        assert doc is not None
        assert doc["invoice_id"] == invoice_id
        assert isinstance(doc["invoice_id"], int)

    def test_invoice_id_immutability(self):
        """Test that updating invoice doesn't regenerate invoice_id."""
        db = get_db()
        
        # Clear collections
        db.invoices.delete_many({})
        db.counters.delete_one({"_id": "invoice"})
        
        # Create invoice
        invoice_id = get_next_invoice_id()
        invoice_doc = {
            "_id": invoice_id,
            "invoice_id": invoice_id,
            "status": "RECEIVED",
            "header": {},
            "created_at": "2024-01-01T00:00:00Z"
        }
        db.invoices.insert_one(invoice_doc)
        
        # Update invoice status (e.g., PUT request)
        db.invoices.update_one(
            {"_id": invoice_id},
            {"$set": {"status": "READY_FOR_POSTING"}}
        )
        
        # Verify invoice_id is unchanged
        doc = db.invoices.find_one({"_id": invoice_id})
        assert doc["invoice_id"] == invoice_id
        assert doc["status"] == "READY_FOR_POSTING"

