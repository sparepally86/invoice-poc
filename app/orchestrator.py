# app/orchestrator.py
import asyncio
import datetime
from app.storage.mongo_client import get_db
from app.agents.validation import run_validation   # adjust import path if different
from app.agents.po_match import run_po_matching   # adjust import path if different

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
    Process a single task. Supports 'process_invoice' tasks.
    Behavior:
      - Load invoice from DB
      - Run ValidationAgent
      - Persist validation result to invoice._workflow.steps
      - If validation requires human -> create human_review task and finish
      - Otherwise run PO matching (if po present) and behave as before
    """
    db = get_db()

    try:
        if task.get("type") != "process_invoice":
            # Unknown task type -> mark error and return
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "unsupported_task_type"}})
            return

        invoice_id = task.get("invoice_id")
        if not invoice_id:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "missing_invoice_id"}})
            return

        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
        if not invoice:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "invoice_not_found"}})
            return

        # --- 1) Validation ---
        validation_out = await asyncio.to_thread(run_validation, db, invoice)

        # persist validation output into invoice document under _workflow.steps
        await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": validation_out}})

        # compute status and set via helper
        new_status = "VALIDATED" if validation_out.get("status") == "completed" else "EXCEPTION"
        from app.utils.state import update_invoice_status
        await asyncio.to_thread(update_invoice_status, db, invoice_id, new_status, "Orchestrator", note="Validation result applied")


        # If validation indicates human required (status not 'completed') -> create human task
        if validation_out.get("status") != "completed":
            now = datetime.datetime.utcnow().isoformat() + "Z"
            human_task = {
                "type": "human_review",
                "invoice_id": invoice_id,
                "status": "pending",
                "created_at": now,
                "payload": {
                    "agent": validation_out.get("agent", "ValidationAgent"),
                    "agent_result": validation_out.get("result", validation_out),
                    "reason": "validation_failed_or_needs_human"
                }
            }
            await asyncio.to_thread(db.tasks.insert_one, human_task)

            # finish original task as done
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
            return

        # --- 2) PO Matching (only if validated) ---
        # re-fetch invoice in case validation added fields
        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
        header = invoice.get("header", {}) if invoice else {}
        po_number = header.get("po_number") or header.get("po") or header.get("po_reference")

        if po_number:
            po_out = await asyncio.to_thread(run_po_matching, db, invoice)

            # persist PO matching result into workflow
            await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": po_out}})

            # set status via helper
            new_status = "MATCHED" if po_out.get("status") == "matched" else "EXCEPTION"
            from app.utils.state import update_invoice_status
            await asyncio.to_thread(update_invoice_status, db, invoice_id, new_status, "Orchestrator", note="PO matching result applied")

            # If PO matching produced issues (partial_match), create a human_review task
            if po_out.get("status") != "matched":
                now = datetime.datetime.utcnow().isoformat() + "Z"
                human_task = {
                    "type": "human_review",
                    "invoice_id": invoice_id,
                    "status": "pending",
                    "created_at": now,
                    "payload": {
                        "agent": po_out.get("agent", "POMatchingAgent"),
                        "agent_result": po_out.get("result", po_out),
                        "reason": "po_partial_or_mismatch"
                    }
                }
                await asyncio.to_thread(db.tasks.insert_one, human_task)

                # finish original processing task
                await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
                return

        # If no PO or PO matched, mark original task done
        now = datetime.datetime.utcnow().isoformat() + "Z"
        await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
    except Exception as e:
        # Log error into the task doc for diagnosability
        try:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": str(e)}})
        except Exception:
            pass

    now = datetime.datetime.utcnow().isoformat() + "Z"
    await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
