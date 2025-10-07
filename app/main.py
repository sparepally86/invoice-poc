# app/main.py (snippet)
from fastapi import FastAPI
from app.api import invoices

app = FastAPI(title="Invoice POC Agentic")

# ---- CORS middleware
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [
    "https://invoice-poc-one.vercel.app/",  # replace with your actual Vercel URL
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

# For quick testing you can use allow_origins=["*"], but lock this down later
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(invoices.router, prefix="/api/v1")

@app.get('/health')
async def health():
    return {'status': 'ok'}
