# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import your router module (ensure this path matches your repo)
from app.api import invoices

app = FastAPI(title="Invoice POC Agentic")

# -------------------- CORS (HERE FIRST) --------------------
# TEMPORARY: use ["*"] to verify quickly. Replace with exact origins later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # <-- change to your Vercel URL once verified
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -----------------------------------------------------------

# Register routers AFTER CORS middleware
app.include_router(invoices.router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # For local run (not used by Render), keep this for convenience
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
