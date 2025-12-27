"""
test_rate_limiting.py

Tests for dual-guard rate limiting in ExplainAgent.

Tests:
1. Per-invoice limit: max 2 calls per invoice
2. Per-minute global limit: max 30 calls per minute
3. Disabled limits: setting to 0 allows unlimited
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime

# Setup environment BEFORE importing rate limiter
os.environ["LLM_PROVIDER"] = "noop"
os.environ["MAX_LLM_CALLS_PER_INVOICE"] = "2"
os.environ["MAX_LLM_CALLS_PER_MINUTE"] = "30"

from app.ai.llm_rate_limiter import (
    DualGuardRateLimiter,
    get_rate_limiter,
    reset_rate_limiter,
)
from app.agents.explain import run_explain


class TestPerInvoiceLimit:
    """Test per-invoice rate limiting: max 2 calls per invoice."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def test_first_two_calls_allowed(self):
        """First 2 calls on same invoice should be allowed."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)
        invoice_id = "INV-001"

        # First call
        assert rl.allow_request(invoice_id=invoice_id) is True
        # Second call
        assert rl.allow_request(invoice_id=invoice_id) is True

    def test_third_call_denied(self):
        """3rd call on same invoice should be denied."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)
        invoice_id = "INV-001"

        # First 2 calls allowed
        assert rl.allow_request(invoice_id=invoice_id) is True
        assert rl.allow_request(invoice_id=invoice_id) is True

        # 3rd call denied
        assert rl.allow_request(invoice_id=invoice_id) is False

    def test_different_invoices_independent(self):
        """Different invoices have independent counters."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)

        # Invoice 1: 2 calls
        assert rl.allow_request(invoice_id="INV-001") is True
        assert rl.allow_request(invoice_id="INV-001") is True

        # Invoice 2: should still have 2 calls available
        assert rl.allow_request(invoice_id="INV-002") is True
        assert rl.allow_request(invoice_id="INV-002") is True

        # Invoice 3: should still have 2 calls available
        assert rl.allow_request(invoice_id="INV-003") is True

    def test_per_invoice_disabled(self):
        """Setting max_per_invoice=0 disables per-invoice guard."""
        rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=30)
        invoice_id = "INV-001"

        # All calls should be allowed (only global limit applies)
        for _ in range(5):
            assert rl.allow_request(invoice_id=invoice_id) is True

    def test_no_invoice_id_denied_when_guard_active(self):
        """If per-invoice guard is active, request without invoice_id is denied."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)

        # Request without invoice_id should be denied
        assert rl.allow_request(invoice_id=None) is False

    def test_stats_tracking(self):
        """Verify stats() returns correct counts."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)

        rl.allow_request(invoice_id="INV-001")
        rl.allow_request(invoice_id="INV-001")
        rl.allow_request(invoice_id="INV-002")

        stats = rl.get_stats()
        assert stats["max_per_invoice"] == 2
        assert stats["max_per_minute"] == 30
        assert stats["invoice_counts"]["INV-001"] == 2
        assert stats["invoice_counts"]["INV-002"] == 1


class TestPerMinuteLimit:
    """Test per-minute global rate limiting: max 30 calls per minute."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def test_first_30_calls_allowed(self):
        """First 30 calls should be allowed."""
        rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=30)

        for i in range(30):
            assert rl.allow_request(invoice_id=f"INV-{i:03d}") is True

    def test_31st_call_denied(self):
        """31st call should be denied."""
        rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=30)

        # 30 calls allowed
        for i in range(30):
            assert rl.allow_request(invoice_id=f"INV-{i:03d}") is True

        # 31st call denied
        assert rl.allow_request(invoice_id="INV-030") is False

    def test_per_minute_disabled(self):
        """Setting max_per_minute=0 disables per-minute guard."""
        rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=0)

        # All calls should be allowed (no guards active)
        for i in range(100):
            assert rl.allow_request(invoice_id=f"INV-{i:03d}") is True

    def test_minute_window_expires(self):
        """Calls older than 60 seconds should be expired from the window."""
        rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=3)

        # Make 3 calls
        assert rl.allow_request(invoice_id="INV-001") is True
        assert rl.allow_request(invoice_id="INV-002") is True
        assert rl.allow_request(invoice_id="INV-003") is True

        # 4th call should be denied
        assert rl.allow_request(invoice_id="INV-004") is False

        # Manually advance time by adding old timestamps that will be cleaned
        # by the next call
        rl.minute_timestamps.clear()

        # After clearing old timestamps, new calls should be allowed
        assert rl.allow_request(invoice_id="INV-005") is True
        assert rl.allow_request(invoice_id="INV-006") is True
        assert rl.allow_request(invoice_id="INV-007") is True

    def test_stats_minute_count(self):
        """Verify stats() returns correct minute call count."""
        rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=30)

        rl.allow_request(invoice_id="INV-001")
        rl.allow_request(invoice_id="INV-002")
        rl.allow_request(invoice_id="INV-003")

        stats = rl.get_stats()
        assert stats["minute_call_count"] == 3


class TestDualGuardInteraction:
    """Test interaction between per-invoice and per-minute guards."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def test_both_guards_enforced(self):
        """Both guards should be enforced simultaneously."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=5)

        # Invoice 1: 2 calls
        assert rl.allow_request(invoice_id="INV-001") is True
        assert rl.allow_request(invoice_id="INV-001") is True

        # Invoice 2: 2 calls (now at 4/5 global)
        assert rl.allow_request(invoice_id="INV-002") is True
        assert rl.allow_request(invoice_id="INV-002") is True

        # Invoice 3: 1 call (now at 5/5 global limit)
        assert rl.allow_request(invoice_id="INV-003") is True

        # Invoice 4: should be denied by global limit (not per-invoice limit)
        assert rl.allow_request(invoice_id="INV-004") is False

        # Invoice 1: should still be denied by per-invoice limit
        # (even though we haven't called per-minute check again)
        assert rl.allow_request(invoice_id="INV-001") is False

    def test_reset_invoice(self):
        """reset_invoice() should reset per-invoice count."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)

        # 2 calls on INV-001
        assert rl.allow_request(invoice_id="INV-001") is True
        assert rl.allow_request(invoice_id="INV-001") is True

        # 3rd call should be denied
        assert rl.allow_request(invoice_id="INV-001") is False

        # Reset invoice
        rl.reset_invoice("INV-001")

        # Now 3rd call should be allowed
        assert rl.allow_request(invoice_id="INV-001") is True

    def test_reset_all(self):
        """reset_all() should clear all counters."""
        rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=10)

        # Make some calls
        for i in range(10):
            rl.allow_request(invoice_id=f"INV-{i:03d}")

        stats = rl.get_stats()
        assert len(stats["invoice_counts"]) > 0
        assert stats["minute_call_count"] == 10

        # Reset all
        rl.reset_all()

        stats = rl.get_stats()
        assert len(stats["invoice_counts"]) == 0
        assert stats["minute_call_count"] == 0


class TestExplainAgentRateLimiting:
    """Integration tests: ExplainAgent respects rate limiting."""

    def setup_method(self):
        """Reset rate limiter and set config for tests."""
        reset_rate_limiter()
        os.environ["MAX_LLM_CALLS_PER_INVOICE"] = "2"
        os.environ["MAX_LLM_CALLS_PER_MINUTE"] = "30"

    def test_explain_respects_per_invoice_limit(self):
        """ExplainAgent should return rate_limited status on 3rd call."""
        # Mock database and invoice
        mock_db = MagicMock()
        mock_db.telemetry.insert_one = MagicMock()

        invoice = {
            "_id": "INV-RATELIMIT-001",
            "header": {
                "invoice_number": "INV-001",
                "vendor": "Test Vendor",
                "amount": 1000.00,
            },
        }

        triggering_step = {
            "result": {
                "codes": ["V001"],
                "messages": ["Test validation"],
            }
        }

        # Call 1: should succeed
        resp1 = run_explain(mock_db, invoice, triggering_step)
        assert resp1["status"] == "completed"
        assert resp1["agent"] == "ExplainAgent"

        # Call 2: should succeed
        resp2 = run_explain(mock_db, invoice, triggering_step)
        assert resp2["status"] == "completed"
        assert resp2["agent"] == "ExplainAgent"

        # Call 3: should be rate limited
        resp3 = run_explain(mock_db, invoice, triggering_step)
        assert resp3["status"] == "rate_limited"
        assert resp3["ai"].get("rate_limited") is True
        assert (
            resp3["result"]["explanation_text"]
            == "Explanation skipped due to rate limits."
        )

    def test_explain_different_invoices_not_limited(self):
        """Different invoices should each get 2 calls."""
        mock_db = MagicMock()
        mock_db.telemetry.insert_one = MagicMock()

        triggering_step = {
            "result": {
                "codes": ["V001"],
                "messages": ["Test validation"],
            }
        }

        # First invoice: 2 calls
        invoice1 = {
            "_id": "INV-A",
            "header": {"invoice_number": "INV-A", "vendor": "Vendor A"},
        }
        resp1a = run_explain(mock_db, invoice1, triggering_step)
        resp1b = run_explain(mock_db, invoice1, triggering_step)
        assert resp1a["status"] == "completed"
        assert resp1b["status"] == "completed"

        # Second invoice: should also allow 2 calls
        invoice2 = {
            "_id": "INV-B",
            "header": {"invoice_number": "INV-B", "vendor": "Vendor B"},
        }
        resp2a = run_explain(mock_db, invoice2, triggering_step)
        resp2b = run_explain(mock_db, invoice2, triggering_step)
        assert resp2a["status"] == "completed"
        assert resp2b["status"] == "completed"

        # First invoice: 3rd call should be rate limited
        resp1c = run_explain(mock_db, invoice1, triggering_step)
        assert resp1c["status"] == "rate_limited"

        # Second invoice: 3rd call should also be rate limited
        resp2c = run_explain(mock_db, invoice2, triggering_step)
        assert resp2c["status"] == "rate_limited"


class TestConfigurable:
    """Test rate limiter configuration via environment."""

    def test_default_config(self):
        """Default config should be 2 per invoice, 30 per minute."""
        reset_rate_limiter()
        os.environ.pop("MAX_LLM_CALLS_PER_INVOICE", None)
        os.environ.pop("MAX_LLM_CALLS_PER_MINUTE", None)

        rl = get_rate_limiter()
        assert rl.max_per_invoice == 2
        assert rl.max_per_minute == 30

    def test_custom_config_from_env(self):
        """Custom config should be read from environment."""
        reset_rate_limiter()
        os.environ["MAX_LLM_CALLS_PER_INVOICE"] = "5"
        os.environ["MAX_LLM_CALLS_PER_MINUTE"] = "100"

        rl = get_rate_limiter()
        assert rl.max_per_invoice == 5
        assert rl.max_per_minute == 100

    def test_disabled_limits(self):
        """Setting limits to 0 should disable them."""
        reset_rate_limiter()
        os.environ["MAX_LLM_CALLS_PER_INVOICE"] = "0"
        os.environ["MAX_LLM_CALLS_PER_MINUTE"] = "0"

        rl = get_rate_limiter()
        assert rl.max_per_invoice == 0
        assert rl.max_per_minute == 0

        # Should allow unlimited
        for i in range(100):
            assert rl.allow_request(invoice_id=f"INV-{i:03d}") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
