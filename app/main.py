# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import dev_vector
from app.api import dev_explain

# Import your router module (ensure this path matches your repo)
from app.api import invoices, masterdata, dev, tasks

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
app.include_router(masterdata.router, prefix="/api/v1")
app.include_router(dev.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(dev_vector.router, prefix="/api/v1")
app.include_router(dev_explain.router, prefix="/api/v1")

# add to app/main.py near the bottom, after router includes
@app.on_event("startup")
async def _start_orchestrator():
    # start the background orchestrator worker
    try:
        from app.orchestrator import start_worker
        start_worker(app)
    except Exception as e:
        print("Failed to start orchestrator:", e)

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # For local run (not used by Render), keep this for convenience
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
