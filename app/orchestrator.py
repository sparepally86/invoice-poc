# app/orchestrator.py
import asyncio
import datetime
from app.storage.mongo_client import get_db
from app.agents.validation import run_validation
from app.agents.po_match import run_po_matching

_worker_task = None
_PEAK_SLEEP = 0.8
_IDLE_SLEEP = 1.5

def start_worker(app):
    """Called in FastAPI startup to start background orchestrator worker."""
    global _worker_task
    if _worker_task is None:
        loop = asyncio.get_event_loop()
        _worker_task = loop.create_task(_worker_loop())
        app.state.orchestrator_task = _worker_task
        print("Orchestrator worker started")

async def _worker_loop():
    db = get_db()
    while True:
        try:
            # find a queued task
            task = await asyncio.to_thread(db.tasks.find_one, {"status": "queued"})
            if not task:
                await asyncio.sleep(_IDLE_SLEEP)
                continue

            # attempt to claim it (simple optimistic)
            claim_res = await asyncio.to_thread(
                db.tasks.update_one,
                {"_id": task["_id"], "status": "queued"},
                {"$set": {"status": "processing", "started_at": datetime.datetime.utcnow().isoformat() + "Z"}}
            )
            if claim_res.modified_count == 0:
                # someone else took it
                await asyncio.sleep(_PEAK_SLEEP)
                continue

            # reload claimed task
            task = await asyncio.to_thread(db.tasks.find_one, {"_id": task["_id"]})
            await process_task(task)
        except Exception as e:
            # log and sleep
            print("Orchestrator loop error:", repr(e))
            await asyncio.sleep(3)

async def process_task(task):
    """
    Process a single task. For now we support 'process_invoice'.
    """
    db = get_db()
    try:
        if task.get("type") == "process_invoice":
            invoice_id = task.get("invoice_id")
            invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
            if not invoice:
                await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "invoice_not_found"}})
                return

            # --- Validation ---
            validation_out = await asyncio.to_thread(run_validation, db, invoice)

            # Persist validation output into invoice document under _workflow.steps
            await asyncio.to_thread(
                db.invoices.update_one,
                {"_id": invoice_id},
                {
                    "$push": {"_workflow.steps": validation_out},
                    "$set": {"status": "VALIDATED" if validation_out["status"] == "completed" else "EXCEPTION"}
                }
            )

            # If validation failed -> mark task done (human will handle)
            if validation_out["status"] != "completed":
                await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": datetime.datetime.utcnow().isoformat() + "Z"}})
                return

            # --- PO Matching (if invoice has PO info) ---
            po_out = await asyncio.to_thread(run_po_matching, db, invoice)
            # persist PO matching
            await asyncio.to_thread(
                db.invoices.update_one,
                {"_id": invoice_id},
                {
                    "$push": {"_workflow.steps": po_out},
                    "$set": {"status": "MATCHED" if po_out["status"] == "matched" else "EXCEPTION"}
                }
            )

            # If PO matching produced issues (partial_match), create a human_review task
            if po_out["status"] != "matched":
                now = datetime.datetime.utcnow().isoformat() + "Z"
                human_task = {
                    "type": "human_review",
                    "invoice_id": invoice_id,
                    "status": "pending",
                    "created_at": now,
                    "payload": {
                        "agent_result": po_out,
                        "reason": "po_partial_or_mismatch"
                    }
                }
                await asyncio.to_thread(db.tasks.insert_one, human_task)

                # finish original processing task
                await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": datetime.datetime.utcnow().isoformat() + "Z"}})
                return

            # If matched, mark done and optionally create next task (e.g., coding)
            # For POC we'll just mark processing done
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": datetime.datetime.utcnow().isoformat() + "Z"}})
        else:
            # unknown task type
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "unsupported_task_type"}})
    except Exception as e:
        await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": str(e)}})
