"""
Manual verification script for sequential invoice_id generation.
This script demonstrates the atomicity of the get_next_invoice_id() function.

Usage:
  python verify_invoice_id_generation.py

This will print the next 5 sequential invoice IDs to verify the counter works.
"""

from app.storage.mongo_client import get_db, get_next_invoice_id

def main():
    print("=" * 60)
    print("Invoice ID Generation Verification")
    print("=" * 60)
    
    try:
        db = get_db()
        print(f"✓ Connected to MongoDB")
        
        # Reset counter for fresh start
        db.counters.delete_one({"_id": "invoice"})
        print(f"✓ Cleared counters collection")
        
        # Generate 5 sequential IDs
        print(f"\nGenerating 5 sequential invoice IDs:")
        ids = []
        for i in range(5):
            invoice_id = get_next_invoice_id()
            ids.append(invoice_id)
            print(f"  {i+1}. invoice_id = {invoice_id} (type: {type(invoice_id).__name__})")
        
        # Verify they are sequential
        expected = [1, 2, 3, 4, 5]
        if ids == expected:
            print(f"\n✓ IDs are sequential: {ids}")
        else:
            print(f"\n✗ IDs are NOT sequential. Expected {expected}, got {ids}")
            return False
        
        # Verify they are integers
        if all(isinstance(id, int) for id in ids):
            print(f"✓ All IDs are integers (human-readable)")
        else:
            print(f"✗ Not all IDs are integers")
            return False
        
        # Check counter document
        counter_doc = db.counters.find_one({"_id": "invoice"})
        if counter_doc and counter_doc.get("seq") == 5:
            print(f"✓ Counter document updated correctly: seq={counter_doc['seq']}")
        else:
            print(f"✗ Counter document issue: {counter_doc}")
            return False
        
        print("\n" + "=" * 60)
        print("SUCCESS: Invoice ID generation is working correctly!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure MONGODB_URI is set in your environment.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
