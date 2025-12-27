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
    
    # Initialize RAG with historical invoices for retrieval
    logger.info("Startup: Initializing RAG vector store with historical invoices...")
    try:
        from app.storage.mongo_client import get_db
        from app.agents.retrieval import index_document
        
        db = get_db()
        # Fetch successful invoices to index
        successful_statuses = ["READY_FOR_POSTING", "CODED", "APPROVED", "POSTED"]
        invoices = list(db.invoices.find({"status": {"$in": successful_statuses}}).limit(20))
        
        indexed_count = 0
        for inv in invoices:
            invoice_id = inv.get("_id", "unknown")
            header = inv.get("header", {}) or {}
            
            # Create indexable text
            parts = [
                "Invoice ID: {}".format(invoice_id),
                "Vendor: {}".format(header.get('vendor_name', 'Unknown')),
                "Amount: {}".format(header.get('amount', 0)),
                "Currency: {}".format(header.get('currency', 'USD'))
            ]
            
            if header.get("po_number"):
                parts.append("PO Number: {}".format(header.get('po_number')))
            
            # Add line items
            lines = inv.get("items") or inv.get("lines") or []
            if lines:
                parts.append("Line Items:")
                for line in lines[:5]:
                    item_text = line.get("item_text", "")
                    amount = line.get("amount", 0)
                    qty = line.get("quantity", 1)
                    parts.append("  - {} (Qty: {}, Amount: {})".format(item_text, qty, amount))
            
            parts.append("Status: {}".format(inv.get('status')))
            text = "\n".join(parts)
            
            # Index with metadata
            metadata = {
                "invoice_id": invoice_id,
                "status": inv.get("status"),
                "vendor": header.get("vendor_name"),
                "amount": header.get("amount"),
                "source": "Past invoice"
            }
            
            try:
                index_document(invoice_id, text, metadata=metadata)
                indexed_count += 1
            except Exception as e:
                logger.warning("Failed to index invoice {}: {}".format(invoice_id, e))
        
        logger.info("Startup: RAG initialized with {} historical invoices".format(indexed_count))
    except Exception as e:
        logger.warning("Startup: RAG initialization skipped or partial: %s", str(e))
    
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
