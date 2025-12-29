from pydantic import BaseModel
from typing import Any, Optional, List

class FieldVal(BaseModel):
    value: Any
    confidence: float

class InvoiceHeader(BaseModel):
    invoice_number: Optional[FieldVal] = None
    invoice_date: Optional[FieldVal] = None
    grand_total: Optional[FieldVal] = None
    invoice_ref: Optional[str] = None
    po_number: Optional[str] = None
    po: Optional[str] = None
    po_reference: Optional[str] = None

class InvoiceLine(BaseModel):
    line_number: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None

class InvoiceValidation(BaseModel):
    status: Optional[str] = None  # e.g., "valid", "requires_review"
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None

class DraftInvoice(BaseModel):
    """
    Minimal invoice for DRAFT status (two-step submission).
    Only identity and source are required.
    """
    vendor: Optional[dict] = None
    source: Optional[dict] = None
    document: Optional[dict] = None
    trace_id: Optional[str] = None

class CanonicalInvoice(BaseModel):
    """
    Complete invoice for RECEIVED status.
    Requires header and lines (minimal full document).
    """
    invoice_id: int  # Sequential, numeric, human-readable RECNO
    trace_id: Optional[str] = None
    status: Optional[str] = None  # "DRAFT", "RECEIVED", "VALIDATED", "MATCHED", "CODED", etc.
    vendor: Optional[dict] = None
    source: Optional[dict] = None
    document: Optional[dict] = None
    header: Optional[InvoiceHeader] = None
    lines: Optional[List[InvoiceLine]] = None
    validation: Optional[InvoiceValidation] = None

