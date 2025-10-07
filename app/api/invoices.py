from fastapi import APIRouter, UploadFile, File, Body
from app.services.agent_orchestrator import plan_and_execute

router = APIRouter()

@router.post('/incoming')
async def incoming(payload: dict = Body(...), file: UploadFile = File(None)):
    return {'invoice_id': 'inv-001', 'status': 1}

@router.post('/invoices/{invoice_id}/process')
async def process(invoice_id: str):
    result = plan_and_execute('dummy text')
    return result

@router.get('/invoices/{invoice_id}')
async def get_invoice(invoice_id: str):
    return {'invoice_id': invoice_id, 'status': 'stub'}
