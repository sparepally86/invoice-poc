"""
Integration test: Invoice lifecycle with schema validation wiring.

Tests the full PUT and POST /submit endpoints with schema validation:
1. Create a DRAFT invoice (should pass without full validation)
2. Transition DRAFT to RECEIVED with invalid data (should fail with 400)
3. Transition DRAFT to RECEIVED with valid data (should succeed)
4. Direct POST /submit with invalid data (should fail with 400)
5. Direct POST /submit with valid data (should succeed)
"""

import asyncio
import json
import httpx
from datetime import datetime


BASE_URL = "http://localhost:8001"

def _now_iso():
    """Return current UTC time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


async def test_draft_creation():
    """Test creating a DRAFT invoice (no full validation required)."""
    print("\n=== Test 1: Create DRAFT Invoice ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/invoices",
            json={
                "vendor": {"name": "Vendor Inc"},
                "source": {"system": "CAPTURE"}
            }
        )
        assert response.status_code == 200, f"Unexpected status: {response.status_code}\n{response.text}"
        data = response.json()
        print(f"✓ Created DRAFT invoice: {data}")
        return data["invoice_id"]


async def test_put_invalid_received():
    """Test PUT with invalid RECEIVED data (missing required fields)."""
    print("\n=== Test 2: PUT with Invalid RECEIVED Data ===")
    
    # First create a DRAFT invoice
    draft_id = await test_draft_creation()
    
    async with httpx.AsyncClient() as client:
        # Try to transition to RECEIVED with incomplete data
        response = await client.put(
            f"{BASE_URL}/api/invoices/{draft_id}",
            json={
                "vendor": {"name": "Vendor Inc"},
                # Missing header, lines, document - will fail validation
                "source": {"system": "CAPTURE"}
            }
        )
        
        # Should get 400 with validation error
        assert response.status_code == 400, f"Expected 400, got {response.status_code}\n{response.text}"
        data = response.json()
        assert "error" in data or "detail" in data, f"Expected error in response: {data}"
        print(f"✓ Correctly rejected invalid RECEIVED: {data}")


async def test_put_valid_received():
    """Test PUT with valid RECEIVED data."""
    print("\n=== Test 3: PUT with Valid RECEIVED Data ===")
    
    # First create a DRAFT invoice
    draft_id = await test_draft_creation()
    
    async with httpx.AsyncClient() as client:
        # Transition to RECEIVED with complete, valid data
        response = await client.put(
            f"{BASE_URL}/api/invoices/{draft_id}",
            json={
                "vendor": {"name": "Vendor Inc"},
                "source": {"system": "CAPTURE", "received_at": _now_iso()},
                "document": {"image_url": "https://example.com/invoice.pdf"},
                "header": {
                    "invoice_number": "INV-001",
                    "invoice_date": "2024-01-01",
                    "vendor_name": "Vendor Inc",
                    "currency": "USD",
                    "total_amount": 1000.00
                },
                "lines": [
                    {
                        "line_number": 1,
                        "description": "Service",
                        "quantity": 1,
                        "line_amount": 1000.00
                    }
                ]
            }
        )
        
        assert response.status_code == 200, f"Unexpected status: {response.status_code}\n{response.text}"
        data = response.json()
        assert data["status"] == "RECEIVED", f"Expected status=RECEIVED, got {data.get('status')}"
        print(f"✓ Successfully transitioned to RECEIVED: invoice_id={draft_id}")


async def test_submit_invalid_received():
    """Test POST /submit with invalid RECEIVED data."""
    print("\n=== Test 4: POST /submit with Invalid Data ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/invoices/submit",
            json={
                "vendor": {"name": "Vendor Inc"},
                "source": {"system": "CAPTURE", "received_at": _now_iso()},
                # Missing header, lines, document - will fail validation
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}\n{response.text}"
        data = response.json()
        assert "error" in data or "detail" in data, f"Expected error in response: {data}"
        print(f"✓ Correctly rejected invalid POST /submit: {data}")


async def test_submit_valid_received():
    """Test POST /submit with valid RECEIVED data."""
    print("\n=== Test 5: POST /submit with Valid Data ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/invoices/submit",
            json={
                "vendor": {"name": "Vendor Inc"},
                "source": {"system": "CAPTURE", "received_at": _now_iso()},
                "document": {"image_url": "https://example.com/invoice.pdf"},
                "header": {
                    "invoice_number": "INV-002",
                    "invoice_date": "2024-01-02",
                    "vendor_name": "Vendor Inc",
                    "currency": "USD",
                    "total_amount": 2000.00
                },
                "lines": [
                    {
                        "line_number": 1,
                        "description": "Service A",
                        "quantity": 2,
                        "line_amount": 2000.00
                    }
                ]
            }
        )
        
        assert response.status_code == 200, f"Unexpected status: {response.status_code}\n{response.text}"
        data = response.json()
        assert data["status"] == "RECEIVED", f"Expected status=RECEIVED, got {data.get('status')}"
        print(f"✓ Successfully created RECEIVED via POST /submit: invoice_id={data['invoice_id']}")


async def main():
    print("=" * 70)
    print("Integration Test: Invoice Lifecycle with Schema Validation")
    print("=" * 70)
    
    try:
        await test_put_invalid_received()
        await test_put_valid_received()
        await test_submit_invalid_received()
        await test_submit_valid_received()
        
        print("\n" + "=" * 70)
        print("✅ All integration tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
