# app/orchestrator.py
import asyncio
import datetime
from app.storage.mongo_client import get_db
from app.agents.validation import run_validation   # adjust import path if different
from app.agents.po_match import run_po_matching   # adjust import path if different
from app.agents.coding import run_coding         # coding agent
from app.agents.risk import run_risk_and_approval  # risk & approval agent
from app.utils.state import update_invoice_status  # centralized status helper
from app.agents.explain import run_explain #explaination agent
from app.utils.normalize_invoice import ensure_minimal_structure

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

def _append_explain_step_to_invoice(db, invoice_id: str, explain_step: dict):
    """
    Append ExplainAgent step dict into invoice._workflow.steps[].
    explain_step should be the agent_response dict produced by run_explain.
    """
    try:
        # ensure timestamp exists
        if "timestamp" not in explain_step:
            explain_step["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        # push into workflow steps array
        db.invoices.update_one({"_id": invoice_id}, {"$push": {"_workflow.steps": explain_step}})
    except Exception:
        # non-fatal: log but do not break orchestrator
        try:
            import logging
            logging.exception("Failed to persist ExplainAgent step for invoice %s", invoice_id)
        except Exception:
            pass


async def process_task(task):
    """
    Process a single task. Supports 'process_invoice' tasks.
    Behavior:
      - Load invoice from DB
      - Run ValidationAgent
      - Persist validation result to invoice._workflow.steps
      - If validation requires human -> create human_review task and finish
      - Otherwise run PO matching (if po present) and behave as before
      - If PO matched -> run CodingAgent, persist result, update status or create human_review
      - After coding/matching run Risk & Approval Agent to auto-approve or create approval task
      - If no human tasks created and no exceptions, mark READY_FOR_POSTING
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
        # normalize invoice to ensure consistent lines/items structure
        invoice = ensure_minimal_structure(invoice)
        if not invoice:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "invoice_not_found"}})
            return

        # Track if we created a human task (then we will not auto-finalize)
        human_task_created = False

        # --- 1) Validation ---
        validation_out = await asyncio.to_thread(run_validation, db, invoice)

        # persist validation output into invoice document under _workflow.steps
        await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": validation_out}})

        # compute status and set via helper
        new_status = "VALIDATED" if validation_out.get("status") == "completed" else "EXCEPTION"
        await asyncio.to_thread(update_invoice_status, db, invoice_id, new_status, "Orchestrator", note="Validation result applied")

        # If validation indicates human required (status not 'completed') -> create human task
        if validation_out.get("status") != "completed":
            # BEFORE creating the human task, call ExplainAgent and persist its step so reviewers see the explanation
            try:
                # use to_thread so sync run_explain doesn't block the event loop
                explain_resp = await asyncio.to_thread(run_explain, db, invoice, validation_out)
                # persist the explain_resp as a workflow step
                await asyncio.to_thread(_append_explain_step_to_invoice, db, invoice_id, explain_resp)
            except Exception:
                # non-fatal; proceed to create human task anyway
                try:
                    import logging
                    logging.exception("ExplainAgent invocation failed for invoice %s during validation path", invoice_id)
                except Exception:
                    pass

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
            human_task_created = True

            # finish original task as done
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})

            # We stop further processing for this invoice until human acts
            return

        # --- 2) PO Matching (only if validated) ---
        # re-fetch invoice in case validation added fields
        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
        invoice = ensure_minimal_structure(invoice)
        header = invoice.get("header", {}) if invoice else {}
        po_number = header.get("po_number") or header.get("po") or header.get("po_reference")

        if po_number:
            po_out = await asyncio.to_thread(run_po_matching, db, invoice)

            # persist PO matching result into workflow
            await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": po_out}})

            # set status via helper
            matched_status = "MATCHED" if po_out.get("status") == "matched" else "EXCEPTION"
            await asyncio.to_thread(update_invoice_status, db, invoice_id, matched_status, "Orchestrator", note="PO matching result applied")

            # If PO matching produced issues (partial_match), create a human_review task
            if po_out.get("status") != "matched":
                # BEFORE creating the human task for PO mismatch, call ExplainAgent to generate context for the reviewer
                try:
                    explain_resp = await asyncio.to_thread(run_explain, db, invoice, po_out)
                    await asyncio.to_thread(_append_explain_step_to_invoice, db, invoice_id, explain_resp)
                except Exception:
                    try:
                        import logging
                        logging.exception("ExplainAgent invocation failed for invoice %s during PO matching path", invoice_id)
                    except Exception:
                        pass

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
                human_task_created = True

                # finish original processing task
                await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})

                # Since PO mismatch, we stop and wait for human review
                return

            # --- 3) CODING (only if PO matched) ---
            # re-fetch invoice again to include any PO-match annotations
            invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
            invoice = ensure_minimal_structure(invoice)
            try:
                coding_out = await asyncio.to_thread(run_coding, db, invoice)
                # persist coding agent output to workflow
                await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": coding_out}})

                coding_status = coding_out.get("status")
                if coding_status == "completed":
                    # mark CODED (uses centralized state helper)
                    await asyncio.to_thread(update_invoice_status, db, invoice_id, "CODED", "Orchestrator", note="Coding applied")

                    # --- 4) RISK & APPROVAL (run after CODED) ---
                    try:
                        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
                        risk_out = await asyncio.to_thread(run_risk_and_approval, db, invoice)
                        # persist risk output
                        await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": risk_out}})

                        # If risk decided auto_approve -> mark READY_FOR_POSTING
                        if risk_out.get("decision") == "auto_approve":
                            await asyncio.to_thread(update_invoice_status, db, invoice_id, "READY_FOR_POSTING", "RiskApprovalAgent", note="Auto-approved by risk rules")
                            # We consider human_task_created still False; we will finalize below

                        elif risk_out.get("status") == "needs_human" or risk_out.get("next_agent") == "ApprovalAgent":
                            # create human approval task entry
                            now = datetime.datetime.utcnow().isoformat() + "Z"
                            approver_task = {
                                "type": "approval",
                                "invoice_id": invoice_id,
                                "status": "pending",
                                "created_at": now,
                                "payload": {
                                    "agent": risk_out.get("agent", "RiskApprovalAgent"),
                                    "agent_result": risk_out.get("result", risk_out),
                                    "suggested_approver": risk_out.get("result", {}).get("suggested_approver", "manager")
                                }
                            }
                            await asyncio.to_thread(db.tasks.insert_one, approver_task)
                            human_task_created = True
                            # set invoice status PENDING_APPROVAL
                            await asyncio.to_thread(update_invoice_status, db, invoice_id, "PENDING_APPROVAL", "Orchestrator", note="Approval task created")
                            # finish original processing task
                            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
                            return
                    except Exception as e:
                        err_step = {
                            "agent": "RiskApprovalAgent",
                            "invoice_id": invoice_id,
                            "status": "failed",
                            "result": {"error": str(e)},
                            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                        }
                        await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": err_step}})
                elif coding_status in ("partial", "failed"):
                    # create human task for coding
                    now = datetime.datetime.utcnow().isoformat() + "Z"
                    human_task = {
                        "type": "human_review",
                        "invoice_id": invoice_id,
                        "status": "pending",
                        "created_at": now,
                        "payload": {
                            "agent": coding_out.get("agent", "CodingAgent"),
                            "agent_result": coding_out.get("result", coding_out),
                            "reason": "coding_partial_or_failed"
                        }
                    }
                    await asyncio.to_thread(db.tasks.insert_one, human_task)
                    human_task_created = True
                    # set invoice to EXCEPTION (or keep MATCHED and flag coding pending)
                    await asyncio.to_thread(update_invoice_status, db, invoice_id, "EXCEPTION", "Orchestrator", note="Coding partial - human review created")
                    # finish original processing task
                    await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
                    return
            except Exception as e:
                # persist a failure step so we can inspect later
                err_step = {
                    "agent": "CodingAgent",
                    "invoice_id": invoice_id,
                    "status": "failed",
                    "result": {"error": str(e)},
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                }
                await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": err_step}})
                # continue — do not block overall pipeline; leave invoice in MATCHED state

        # At this point: either there was no PO, or PO matched + coding (if any) handled.
        # If no human tasks were created and invoice is not in an exception/pending state,
        # mark it READY_FOR_POSTING so it can be posted later by ERP integration or considered final.
        try:
            invoice_latest = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
            current_status = (invoice_latest.get("status") if invoice_latest else None)
            # Do not override statuses that require human action or are already final
            if not human_task_created and current_status not in ("PENDING_APPROVAL", "EXCEPTION", "REJECTED", "READY_FOR_POSTING", "POSTED"):
                await asyncio.to_thread(update_invoice_status, db, invoice_id, "READY_FOR_POSTING", "Orchestrator", note="All agents completed — ready for posting")
        except Exception as _e:
            # If status update fails, persist a workflow step but continue
            err_step = {
                "agent": "Orchestrator",
                "invoice_id": invoice_id,
                "status": "failed_to_set_final_status",
                "result": {"error": str(_e)},
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            }
            await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": err_step}})

        # If no early returns were triggered, mark original task done
        now = datetime.datetime.utcnow().isoformat() + "Z"
        await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
        return

    except Exception as e:
        # Log error into the task doc for diagnosability
        try:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": str(e)}})
        except Exception:
            pass

        # ensure task is marked done/failed with timestamp
        now = datetime.datetime.utcnow().isoformat() + "Z"
        try:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "finished_at": now}})
        except Exception:
            pass
