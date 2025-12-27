#!/usr/bin/env python3
"""
Demo script: Dual-guard rate limiting behavior
"""

import os
os.environ["MAX_LLM_CALLS_PER_INVOICE"] = "2"
os.environ["MAX_LLM_CALLS_PER_MINUTE"] = "30"

from app.ai.llm_rate_limiter import DualGuardRateLimiter, reset_rate_limiter

# Demo 1: Per-invoice limit
print("=== DEMO 1: Per-Invoice Limit (max 2 per invoice) ===")
reset_rate_limiter()
rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=30)

invoice = "INV-001"
for i in range(1, 5):
    allowed = rl.allow_request(invoice_id=invoice)
    status = "✓ ALLOWED" if allowed else "✗ DENIED (rate limited)"
    print(f"  Call {i} on {invoice}: {status}")

# Demo 2: Per-minute limit
print("\n=== DEMO 2: Per-Minute Global Limit (max 5 per minute) ===")
reset_rate_limiter()
rl = DualGuardRateLimiter(max_per_invoice=0, max_per_minute=5)

for i in range(1, 8):
    allowed = rl.allow_request(invoice_id=f"INV-{i:03d}")
    status = "✓ ALLOWED" if allowed else "✗ DENIED (rate limited)"
    print(f"  Call {i} (global): {status}")

# Demo 3: Both guards
print("\n=== DEMO 3: Both Guards Active (2 per invoice, 5 per minute) ===")
reset_rate_limiter()
rl = DualGuardRateLimiter(max_per_invoice=2, max_per_minute=5)

calls = [
    ("INV-A", "call 1"),
    ("INV-A", "call 2"),
    ("INV-B", "call 1"),
    ("INV-B", "call 2"),
    ("INV-C", "call 1 - global at 5/5"),
    ("INV-D", "call 1 - exceeds global"),
]

for i, (inv_id, reason) in enumerate(calls, 1):
    allowed = rl.allow_request(invoice_id=inv_id)
    status = "✓ ALLOWED" if allowed else "✗ DENIED"
    print(f"  Call {i} on {inv_id}: {status:12} ({reason})")

print("\n=== All demos completed successfully ===")
