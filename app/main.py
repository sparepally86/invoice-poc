# app/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize logging FIRST, before any other app imports
from app.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

from app.api import dev_vector  # noqa: E402
from app.api import dev_explain  # noqa: E402
from app.api import dev_reindex_feedback, dev_retrieve  # noqa: E402

# Import your router module (ensure this path matches your repo)
from app.api import invoices, masterdata, dev, tasks  # noqa: E402
from app.api import explain, feedback  # noqa: E402

logger.info("Starting Invoice POC Agentic application")


# -------------------- LIFESPAN CONTEXT MANAGER --------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    This is the modern FastAPI approach (replaces deprecated @app.on_event).
    """
    # Startup phase
    logger.info("Startup: Initializing orchestrator worker...")
    try:
        from app.orchestrator import start_worker
        start_worker(app)
        logger.info("Startup: Orchestrator worker started successfully")
    except Exception as e:
        logger.exception("CRITICAL: Failed to start orchestrator worker - invoices will not be processed! Error: %s", str(e))
        # Don't re-raise - allow app to continue but log the issue
    
    yield  # Application runs here
    
    # Shutdown phase (optional - cleanup resources if needed)
    logger.info("Shutdown: Cleaning up resources...")
    # Add any cleanup code here if needed


app = FastAPI(title="Invoice POC Agentic", lifespan=lifespan)

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
app.include_router(explain.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")

# Routers with absolute paths defined internally (already include /api/v1 in route decorators)
app.include_router(dev_reindex_feedback.router)
app.include_router(dev_retrieve.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # For local run (not used by Render), keep this for convenience
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
