from pydantic import BaseModel
from typing import Any, Optional

class FieldVal(BaseModel):
    value: Any
    confidence: float

class InvoiceHeader(BaseModel):
    invoice_number: Optional[FieldVal]
    invoice_date: Optional[FieldVal]
    grand_total: Optional[FieldVal]

class CanonicalInvoice(BaseModel):
    invoice_id: str
    header: InvoiceHeader
    vendor: Optional[dict]
    validation: dict
