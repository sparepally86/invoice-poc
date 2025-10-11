# tests/test_vector_client.py
from app.storage.vector_client import get_vector_client

def test_vector_upsert_and_search():
    vc = get_vector_client()

    # clean slate (for idempotent test runs in same process)
    # we can't clear private store from outside easily, so use unique ids
    doc1 = "Invoice #1: Office chairs and tables, GST 18% applied to line items. Delivery to Mumbai."
    doc2 = "Invoice #2: Laptop purchase, tax exempt, delivery to Hyderabad. PO ref: PO-55."

    r1 = vc.upsert("doc-inv-1", doc1, metadata={"type":"invoice", "loc":"mumbai"})
    r2 = vc.upsert("doc-inv-2", doc2, metadata={"type":"invoice", "loc":"hyd"})

    assert r1["ok"] and r2["ok"]

    # deterministic search: query with 'laptop' should hit doc-inv-2 first
    res = vc.search("laptop purchase", k=3)
    assert isinstance(res, list)
    assert len(res) >= 1
    assert res[0]["id"] == "doc-inv-2"

    # query with 'GST' should hit doc-inv-1
    res2 = vc.search("GST 18% chairs", k=3)
    assert len(res2) >= 1
    assert res2[0]["id"] == "doc-inv-1"

    # filter by metadata: only return docs matching metadata
    res3 = vc.search("delivery", k=5, filter={"loc":"mumbai"})
    # should return doc-inv-1 (mumbai)
    assert any(r["id"] == "doc-inv-1" for r in res3)
