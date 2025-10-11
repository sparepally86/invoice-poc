# app/ai/llm_rate_limiter.py
"""
Simple in-memory token-bucket style rate limiter for LLM calls.

Usage:
  from app.ai.llm_rate_limiter import get_rate_limiter
  rl = get_rate_limiter()
  allowed = rl.allow_request(cost=1)  # cost can represent tokens or call weight
"""

import os
import threading
import time

class RateLimiter:
    def __init__(self, capacity: int = 60, refill_rate_per_sec: float = 1.0):
        """
        capacity: max tokens in bucket (default 60)
        refill_rate_per_sec: how many tokens are added per second (default 1/sec => 60/min)
        """
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def allow_request(self, cost: float = 1.0) -> bool:
        """
        Try to consume `cost` tokens. Return True if allowed.
        """
        with self._lock:
            self._refill()
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False

# singleton accessor
_global_rl = None

def get_rate_limiter() -> RateLimiter:
    global _global_rl
    if _global_rl is None:
        # read config from env (optional)
        try:
            cap = int(os.environ.get("LLM_RATE_LIMIT_CAPACITY", "60"))
            per_min = int(os.environ.get("LLM_RATE_LIMIT_PER_MINUTE", "60"))
            # convert per_min to refill/sec
            refill_per_sec = float(per_min) / 60.0 if per_min > 0 else 1.0
            _global_rl = RateLimiter(capacity=cap, refill_rate_per_sec=refill_per_sec)
        except Exception:
            _global_rl = RateLimiter()
    return _global_rl
