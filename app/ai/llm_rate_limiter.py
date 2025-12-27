# app/ai/llm_rate_limiter.py
"""
Dual-guard rate limiter for LLM calls:
  1. Per-invoice limit: MAX_LLM_CALLS_PER_INVOICE (default 2)
  2. Per-minute global limit: MAX_LLM_CALLS_PER_MINUTE (default 30)

Both guards are local, in-memory, and deterministic.
Set limits to 0 to disable.

Usage:
  from app.ai.llm_rate_limiter import get_rate_limiter
  rl = get_rate_limiter()
  allowed = rl.allow_request(invoice_id="inv-123")  # Uses both guards
"""

import os
import threading
import time
from collections import deque
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DualGuardRateLimiter:
    """
    Implements two independent rate limit guards:
    
    Guard 1: Per-Invoice
    - Each invoice_id can trigger at most MAX_LLM_CALLS_PER_INVOICE LLM calls
    - Tracked in memory: dict[invoice_id] -> call_count
    - Never expires (lifetime of process)
    
    Guard 2: Per-Minute Global
    - Process-wide: at most MAX_LLM_CALLS_PER_MINUTE LLM calls per minute
    - Tracked in memory: deque of timestamps (sliding window)
    - Auto-expires: entries older than 60 seconds dropped
    
    If either limit is exceeded, request is denied (deterministic fallback).
    If either limit is set to 0, that guard is disabled.
    """

    def __init__(self, max_per_invoice: int = 2, max_per_minute: int = 30):
        """
        Args:
            max_per_invoice: Max LLM calls per unique invoice_id (0 = disabled)
            max_per_minute: Max LLM calls per minute process-wide (0 = disabled)
        """
        self.max_per_invoice = max(0, max_per_invoice)
        self.max_per_minute = max(0, max_per_minute)
        
        # Per-invoice call count tracker: {invoice_id: count}
        self.invoice_call_counts: dict[str, int] = {}
        
        # Per-minute global tracker: deque of timestamps (epoch seconds)
        self.minute_timestamps: deque = deque()
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info(
            f"DualGuardRateLimiter initialized: "
            f"max_per_invoice={self.max_per_invoice}, "
            f"max_per_minute={self.max_per_minute}"
        )

    def allow_request(self, invoice_id: Optional[str] = None) -> bool:
        """
        Check both guards. Return True if allowed, False if either limit exceeded.
        
        Args:
            invoice_id: Unique invoice identifier (required for per-invoice guard)
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        with self._lock:
            now = time.time()
            
            # GUARD 1: Per-invoice limit
            if self.max_per_invoice > 0:
                if not invoice_id:
                    # If no invoice_id provided but per-invoice guard is active, deny
                    logger.warning("Rate limiter: per-invoice guard active but no invoice_id provided")
                    return False
                
                current_count = self.invoice_call_counts.get(invoice_id, 0)
                if current_count >= self.max_per_invoice:
                    logger.warning(
                        f"Rate limit: per-invoice limit exceeded for invoice_id={invoice_id} "
                        f"({current_count}/{self.max_per_invoice})"
                    )
                    return False
            
            # GUARD 2: Per-minute global limit
            if self.max_per_minute > 0:
                # Clean old timestamps (> 60 seconds old)
                cutoff = now - 60.0
                while self.minute_timestamps and self.minute_timestamps[0] < cutoff:
                    self.minute_timestamps.popleft()
                
                # Check if we've hit the limit
                if len(self.minute_timestamps) >= self.max_per_minute:
                    logger.warning(
                        f"Rate limit: per-minute global limit exceeded "
                        f"({len(self.minute_timestamps)}/{self.max_per_minute})"
                    )
                    return False
                
                # Add this request to the timeline
                self.minute_timestamps.append(now)
            
            # BOTH GUARDS PASSED: Record the per-invoice call
            if self.max_per_invoice > 0 and invoice_id:
                current_count = self.invoice_call_counts.get(invoice_id, 0)
                self.invoice_call_counts[invoice_id] = current_count + 1
                logger.debug(
                    f"Rate limit: request allowed for invoice_id={invoice_id} "
                    f"({current_count + 1}/{self.max_per_invoice})"
                )
            
            return True

    def reset_invoice(self, invoice_id: str) -> None:
        """
        Reset per-invoice call count (for testing or manual override).
        """
        with self._lock:
            if invoice_id in self.invoice_call_counts:
                del self.invoice_call_counts[invoice_id]
                logger.info(f"Rate limit: reset per-invoice count for invoice_id={invoice_id}")

    def reset_all(self) -> None:
        """
        Reset all counters (for testing).
        """
        with self._lock:
            self.invoice_call_counts.clear()
            self.minute_timestamps.clear()
            logger.info("Rate limit: reset all counters")

    def get_stats(self) -> dict:
        """
        Return current state for debugging/monitoring.
        """
        with self._lock:
            return {
                "max_per_invoice": self.max_per_invoice,
                "max_per_minute": self.max_per_minute,
                "invoice_counts": dict(self.invoice_call_counts),
                "minute_call_count": len(self.minute_timestamps),
            }


# Singleton accessor
_global_rl: Optional[DualGuardRateLimiter] = None


def get_rate_limiter() -> DualGuardRateLimiter:
    """
    Get or create the global rate limiter singleton.
    Reads config from environment variables:
      - MAX_LLM_CALLS_PER_INVOICE (default: 2)
      - MAX_LLM_CALLS_PER_MINUTE (default: 30)
    """
    global _global_rl
    if _global_rl is None:
        try:
            max_per_invoice = int(os.environ.get("MAX_LLM_CALLS_PER_INVOICE", "2"))
            max_per_minute = int(os.environ.get("MAX_LLM_CALLS_PER_MINUTE", "30"))
        except (ValueError, TypeError):
            max_per_invoice = 2
            max_per_minute = 30
        
        _global_rl = DualGuardRateLimiter(
            max_per_invoice=max_per_invoice,
            max_per_minute=max_per_minute
        )
    return _global_rl


def reset_rate_limiter() -> None:
    """
    Reset the rate limiter singleton (for testing).
    """
    global _global_rl
    _global_rl = None
