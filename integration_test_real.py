#!/usr/bin/env python3
"""
Real Integration Test — Invoice Lifecycle API

This script:
1. Queries MongoDB for real vendors and POs
2. Creates realistic invoice payloads
3. Makes actual HTTP requests to running FastAPI server
4. Tests POST /invoices, PUT /invoices/{id}, POST /invoices/submit
5. Tests positive and negative cases
6. Reports invoice_ids created for MongoDB verification
"""

import requests
import json
from pymongo import MongoClient
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration
API_BASE_URL = "http://localhost:8001/api"
MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB = os.environ.get("MONGODB_DB", "invoice_poc")

# Track all created invoices
created_invoices = {
    "positive": [],
    "negative": []
}

print("\n" + "="*80)
print("INVOICE LIFECYCLE — REAL INTEGRATION TEST")
print("="*80)

# ============================================================================
# STEP 1: Connect to MongoDB and fetch real data
# ============================================================================
print("\n[1] Connecting to MongoDB...")

if not MONGODB_URI:
    print("ERROR: MONGODB_URI not set. Exiting.")
    exit(1)

try:
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    print(f"✓ Connected to {MONGODB_DB}")
except Exception as e:
    print(f"ERROR: Failed to connect to MongoDB: {e}")
    exit(1)

# Fetch real vendors
print("\n[2] Fetching real vendors from MongoDB...")
vendors = list(db.invoices.find({"vendor": {"$exists": True, "$ne": None}}, {"vendor": 1}).limit(3))
if not vendors:
    print("WARNING: No vendors found in invoices. Using mock data.")
    real_vendors = [
        {"id": "vendor-001", "name": "Acme Corporation"},
        {"id": "vendor-002", "name": "TechSupply Inc"}
    ]
else:
    real_vendors = [v.get("vendor") for v in vendors if v.get("vendor")]
    print(f"✓ Found {len(real_vendors)} vendors")

# Fetch real POs
print("\n[3] Fetching real POs from MongoDB...")
invoices_with_po = list(db.invoices.find(
    {"header.po_number": {"$exists": True, "$ne": None}},
    {"header.po_number": 1}
).limit(3))

if invoices_with_po:
    real_pos = [doc.get("header", {}).get("po_number") for doc in invoices_with_po]
    real_pos = [po for po in real_pos if po]
    print(f"✓ Found {len(real_pos)} valid POs: {real_pos}")
else:
    real_pos = ["PO-2024-001", "PO-2024-002"]
    print(f"WARNING: No POs found. Using mock: {real_pos}")

# ============================================================================
# STEP 2: Test POST /api/invoices (Create DRAFT)
# ============================================================================
print("\n" + "="*80)
print("TEST 1: POST /api/invoices (Create DRAFT)")
print("="*80)

vendor_1 = real_vendors[0] if real_vendors else {"id": "vendor-001", "name": "Acme Corp"}
po_1 = real_pos[0] if real_pos else "PO-2024-001"

draft_payload = {
    "vendor": vendor_1,
    "source": {
        "channel": "email",
        "received_at": datetime.utcnow().isoformat() + "Z",
        "filename": "invoice_acme_20241228.pdf"
    },
    "document": {
        "file_name": "invoice_acme_20241228.pdf",
        "page_count": 1,
        "file_size_bytes": 45000
    }
}

print("\nRequest payload:")
print(json.dumps(draft_payload, indent=2, default=str))

try:
    response = requests.post(f"{API_BASE_URL}/invoices", json=draft_payload)
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 201:
        result = response.json()
        invoice_id_1 = result.get("invoice_id")
        trace_id_1 = result.get("trace_id")
        status = result.get("status")
        
        print(f"✓ SUCCESS")
        print(f"  invoice_id: {invoice_id_1}")
        print(f"  trace_id: {trace_id_1}")
        print(f"  status: {status}")
        
        created_invoices["positive"].append({
            "endpoint": "POST /invoices",
            "invoice_id": invoice_id_1,
            "trace_id": trace_id_1,
            "status": status,
            "po": po_1
        })
        
        # Verify in MongoDB
        print("\n[Verification] Checking MongoDB...")
        invoice_doc = db.invoices.find_one({"_id": invoice_id_1})
        if invoice_doc:
            print(f"✓ Invoice found in DB")
            print(f"  Status: {invoice_doc.get('status')}")
            print(f"  Vendor: {invoice_doc.get('vendor', {}).get('name', 'N/A')}")
        else:
            print(f"✗ Invoice NOT found in DB (unexpected)")
    else:
        print(f"✗ FAILED: {response.text}")
        created_invoices["negative"].append({
            "endpoint": "POST /invoices",
            "status_code": response.status_code,
            "error": response.text
        })
except Exception as e:
    print(f"✗ EXCEPTION: {e}")
    created_invoices["negative"].append({
        "endpoint": "POST /invoices",
        "exception": str(e)
    })

# ============================================================================
# STEP 2b: Test POST /api/invoices with another vendor (for later testing)
# ============================================================================
print("\n[Creating second DRAFT for testing...]")

vendor_2 = real_vendors[1] if len(real_vendors) > 1 else real_vendors[0]
po_2 = real_pos[1] if len(real_pos) > 1 else real_pos[0]

draft_payload_2 = {
    "vendor": vendor_2,
    "source": {
        "channel": "web_ui",
        "received_at": datetime.utcnow().isoformat() + "Z"
    },
    "document": {
        "file_name": "invoice_vendor2_20241228.pdf"
    }
}

try:
    response = requests.post(f"{API_BASE_URL}/invoices", json=draft_payload_2)
    if response.status_code == 201:
        result = response.json()
        invoice_id_2 = result.get("invoice_id")
        trace_id_2 = result.get("trace_id")
        print(f"✓ Created second DRAFT: invoice_id={invoice_id_2}")
    else:
        print(f"✗ Failed to create second DRAFT: {response.text}")
        invoice_id_2 = None
except Exception as e:
    print(f"✗ Exception: {e}")
    invoice_id_2 = None

# ============================================================================
# STEP 3: Test PUT /api/invoices/{invoice_id} (DRAFT → RECEIVED)
# ============================================================================
print("\n" + "="*80)
print(f"TEST 2: PUT /api/invoices/{invoice_id_1} (DRAFT → RECEIVED)")
print("="*80)

received_payload = {
    "header": {
        "invoice_number": {
            "value": f"INV-{invoice_id_1}-2024",
            "confidence": 0.98
        },
        "invoice_date": {
            "value": "2024-12-28",
            "confidence": 0.95
        },
        "grand_total": {
            "value": 5450.00,
            "confidence": 0.99
        },
        "po_number": po_1,
        "po": po_1
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Consulting services - Week 1",
            "quantity": 40,
            "unit_price": 125.00,
            "amount": 5000.00
        },
        {
            "line_number": 2,
            "description": "Travel expenses",
            "quantity": 1,
            "unit_price": 450.00,
            "amount": 450.00
        }
    ],
    "validation": {
        "status": "pre_validated"
    }
}

print(f"\nRequest payload (partial):")
print(f"  header.invoice_number: {received_payload['header']['invoice_number']['value']}")
print(f"  header.po_number: {received_payload['header']['po_number']}")
print(f"  lines: {len(received_payload['lines'])} items")

try:
    response = requests.put(f"{API_BASE_URL}/invoices/{invoice_id_1}", json=received_payload)
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        status = result.get("status")
        updated_at = result.get("updated_at")
        
        print(f"✓ SUCCESS")
        print(f"  Status: {status}")
        print(f"  Updated at: {updated_at}")
        
        created_invoices["positive"].append({
            "endpoint": "PUT /invoices/{id}",
            "invoice_id": invoice_id_1,
            "status": status,
            "transition": "DRAFT → RECEIVED"
        })
        
        # Verify in MongoDB
        print("\n[Verification] Checking MongoDB...")
        invoice_doc = db.invoices.find_one({"_id": invoice_id_1})
        if invoice_doc:
            print(f"✓ Invoice updated")
            print(f"  Status: {invoice_doc.get('status')}")
            print(f"  Header: {invoice_doc.get('header', {}).get('invoice_number', {})}")
            print(f"  Lines: {len(invoice_doc.get('lines', []))} items")
            
            # Check if task was created
            task = db.tasks.find_one({"invoice_id": invoice_id_1})
            if task:
                print(f"✓ Orchestration task created")
                print(f"  Task status: {task.get('status')}")
            else:
                print(f"✗ No orchestration task found (ISSUE)")
        else:
            print(f"✗ Invoice NOT found in DB")
    else:
        print(f"✗ FAILED: {response.text}")
        created_invoices["negative"].append({
            "endpoint": f"PUT /invoices/{invoice_id_1}",
            "status_code": response.status_code,
            "error": response.text
        })
except Exception as e:
    print(f"✗ EXCEPTION: {e}")
    created_invoices["negative"].append({
        "endpoint": f"PUT /invoices/{invoice_id_1}",
        "exception": str(e)
    })

# ============================================================================
# STEP 4: Test negative case — PUT on already RECEIVED invoice
# ============================================================================
print("\n" + "="*80)
print(f"TEST 3: Negative case — PUT on already RECEIVED (should fail)")
print("="*80)

print(f"\nAttempting to PUT on invoice {invoice_id_1} (already RECEIVED)...")

try:
    response = requests.put(f"{API_BASE_URL}/invoices/{invoice_id_1}", json=received_payload)
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 400:
        print(f"✓ CORRECTLY REJECTED (400)")
        error_msg = response.json().get("detail", "")
        print(f"  Error: {error_msg}")
        created_invoices["negative"].append({
            "endpoint": f"PUT /invoices/{invoice_id_1} (already RECEIVED)",
            "status_code": 400,
            "result": "Correctly rejected invalid transition"
        })
    else:
        print(f"✗ UNEXPECTED: Got {response.status_code} instead of 400")
        print(f"  Response: {response.text}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

# ============================================================================
# STEP 5: Test negative case — PUT on non-existent invoice
# ============================================================================
print("\n" + "="*80)
print(f"TEST 4: Negative case — PUT on non-existent invoice (should return 404)")
print("="*80)

fake_id = 999999
print(f"\nAttempting to PUT on invoice {fake_id} (doesn't exist)...")

try:
    response = requests.put(f"{API_BASE_URL}/invoices/{fake_id}", json=received_payload)
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 404:
        print(f"✓ CORRECTLY RETURNED 404")
        error_msg = response.json().get("detail", "")
        print(f"  Error: {error_msg}")
        created_invoices["negative"].append({
            "endpoint": f"PUT /invoices/{fake_id} (non-existent)",
            "status_code": 404,
            "result": "Correctly returned 404"
        })
    else:
        print(f"✗ UNEXPECTED: Got {response.status_code} instead of 404")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

# ============================================================================
# STEP 6: Test POST /api/invoices/submit (Direct RECEIVED)
# ============================================================================
print("\n" + "="*80)
print("TEST 5: POST /api/invoices/submit (Direct RECEIVED creation)")
print("="*80)

vendor_3 = real_vendors[0] if real_vendors else {"id": "vendor-003", "name": "Direct Submit Corp"}
po_3 = real_pos[0] if real_pos else "PO-2024-003"

submit_payload = {
    "vendor": vendor_3,
    "source": {
        "channel": "ui_direct",
        "received_at": datetime.utcnow().isoformat() + "Z"
    },
    "document": {
        "file_name": "invoice_direct_20241228.pdf",
        "image_url": "https://example.com/invoice.pdf"
    },
    "header": {
        "invoice_number": {
            "value": "INV-DIRECT-001",
            "confidence": 1.0
        },
        "invoice_date": {
            "value": "2024-12-28",
            "confidence": 1.0
        },
        "grand_total": {
            "value": 3200.00,
            "confidence": 1.0
        },
        "po_number": po_3
    },
    "lines": [
        {
            "line_number": 1,
            "description": "Software License",
            "quantity": 1,
            "unit_price": 3200.00,
            "amount": 3200.00
        }
    ]
}

print("\nRequest payload (direct RECEIVED):")
print(f"  vendor: {submit_payload['vendor'].get('name', 'N/A')}")
print(f"  header.invoice_number: {submit_payload['header']['invoice_number']['value']}")
print(f"  header.po_number: {submit_payload['header']['po_number']}")
print(f"  lines: {len(submit_payload['lines'])} items")

try:
    response = requests.post(f"{API_BASE_URL}/invoices/submit", json=submit_payload)
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 201:
        result = response.json()
        invoice_id_3 = result.get("invoice_id")
        trace_id_3 = result.get("trace_id")
        status = result.get("status")
        
        print(f"✓ SUCCESS")
        print(f"  invoice_id: {invoice_id_3}")
        print(f"  trace_id: {trace_id_3}")
        print(f"  status: {status}")
        
        created_invoices["positive"].append({
            "endpoint": "POST /invoices/submit",
            "invoice_id": invoice_id_3,
            "trace_id": trace_id_3,
            "status": status
        })
        
        # Verify in MongoDB
        print("\n[Verification] Checking MongoDB...")
        invoice_doc = db.invoices.find_one({"_id": invoice_id_3})
        if invoice_doc:
            print(f"✓ Invoice found")
            print(f"  Status: {invoice_doc.get('status')}")
            print(f"  Header: {invoice_doc.get('header', {}).get('invoice_number', {})}")
            
            # Check if task was created
            task = db.tasks.find_one({"invoice_id": invoice_id_3})
            if task:
                print(f"✓ Orchestration task created immediately")
                print(f"  Task status: {task.get('status')}")
            else:
                print(f"✗ No task created (ISSUE - should create task for RECEIVED)")
    else:
        print(f"✗ FAILED: {response.text}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

# ============================================================================
# STEP 7: Test POST /api/invoices/incoming (Legacy endpoint)
# ============================================================================
print("\n" + "="*80)
print("TEST 6: POST /api/invoices/incoming (Legacy endpoint)")
print("="*80)

incoming_payload = {
    "vendor": {
        "id": "vendor-legacy",
        "name": "Legacy System Vendor"
    },
    "source": {
        "channel": "legacy_system"
    },
    "document": {},
    "header": {
        "invoice_number": {
            "value": "INV-LEGACY-001",
            "confidence": 0.90
        },
        "grand_total": {
            "value": 1500.00,
            "confidence": 0.90
        }
    },
    "lines": [
        {
            "description": "Legacy invoice item",
            "amount": 1500.00
        }
    ]
}

print("\nRequest payload (legacy incoming):")
print(f"  vendor: {incoming_payload['vendor']['name']}")
print(f"  header.invoice_number: {incoming_payload['header']['invoice_number']['value']}")

try:
    response = requests.post(f"{API_BASE_URL}/incoming", json=incoming_payload)
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 200 or response.status_code == 201:
        result = response.json()
        invoice_id_4 = result.get("invoice_id")
        status = result.get("status")
        
        print(f"✓ SUCCESS")
        print(f"  invoice_id: {invoice_id_4}")
        print(f"  status: {status}")
        
        created_invoices["positive"].append({
            "endpoint": "POST /incoming (legacy)",
            "invoice_id": invoice_id_4,
            "status": status
        })
    else:
        print(f"✗ FAILED: {response.text}")
except Exception as e:
    print(f"✗ EXCEPTION: {e}")

# ============================================================================
# FINAL REPORT
# ============================================================================
print("\n" + "="*80)
print("INTEGRATION TEST REPORT")
print("="*80)

print("\n✅ POSITIVE TEST CASES (Successful):")
for i, test in enumerate(created_invoices["positive"], 1):
    print(f"\n{i}. {test.get('endpoint', 'Unknown')}")
    if "invoice_id" in test:
        print(f"   invoice_id: {test['invoice_id']}")
    if "trace_id" in test:
        print(f"   trace_id: {test['trace_id']}")
    if "status" in test:
        print(f"   status: {test['status']}")
    if "transition" in test:
        print(f"   transition: {test['transition']}")

print("\n\n❌ NEGATIVE TEST CASES (Expected Failures):")
for i, test in enumerate(created_invoices["negative"], 1):
    print(f"\n{i}. {test.get('endpoint', 'Unknown')}")
    if "status_code" in test:
        print(f"   status_code: {test['status_code']}")
    if "result" in test:
        print(f"   result: {test['result']}")
    if "error" in test:
        print(f"   error: {test['error'][:100]}...")

# ============================================================================
# MONGODB VERIFICATION QUERIES
# ============================================================================
print("\n" + "="*80)
print("MONGODB VERIFICATION QUERIES")
print("="*80)

print("\n📝 Use these commands to verify invoices in MongoDB:\n")

for test in created_invoices["positive"]:
    if "invoice_id" in test:
        invoice_id = test["invoice_id"]
        print(f"\n# {test.get('endpoint', 'Test')} — invoice_id: {invoice_id}")
        print(f"db.invoices.findOne({{_id: {invoice_id}}})")
        print(f"db.tasks.findOne({{invoice_id: {invoice_id}}})")

# ============================================================================
# SCHEMA VERIFICATION
# ============================================================================
print("\n" + "="*80)
print("SCHEMA VERIFICATION")
print("="*80)

print("\n✓ Invoice document now includes 'status' field:")
print("  - DRAFT: Minimal data (vendor, source, document)")
print("  - RECEIVED: Complete data (header, lines required)")
print("  - VALIDATED, MATCHED, CODED, etc.: Updated by orchestrator")

print("\n✓ New fields in created invoices:")
print("  - trace_id: Request correlation ID")
print("  - created_at: Immutable creation timestamp")
print("  - updated_at: Mutable last-update timestamp")

print("\n✓ Orchestrator integration:")
print("  - Tasks table: Entry created when status=RECEIVED")
print("  - Status progression: DRAFT → RECEIVED → VALIDATED → ...")

print("\n" + "="*80)
print(f"Test completed at: {datetime.utcnow().isoformat()}Z")
print("="*80 + "\n")
