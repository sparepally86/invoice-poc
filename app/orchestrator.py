# app/orchestrator.py
import asyncio
import datetime
from app.storage.mongo_client import get_db
from app.agents.validation import run_validation

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
    Process a single task. For now we only support 'process_invoice'.
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

            # Mark task done
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": datetime.datetime.utcnow().isoformat() + "Z"}})
        else:
            # unknown task type
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "unsupported_task_type"}})
    except Exception as e:
        await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": str(e)}})
