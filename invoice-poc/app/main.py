from fastapi import FastAPI
from app.api import invoices

app = FastAPI(title='Invoice POC Agentic')
app.include_router(invoices.router, prefix='/api/v1')

@app.get('/health')
async def health():
    return {'status': 'ok'}
