# app/orchestrator.py
import asyncio
import datetime
from typing import Optional
from app.logging_config import get_logger
from app.storage.mongo_client import get_db
from app.agents.validation import run_validation
from app.agents.po_match import run_po_matching
from app.agents.coding import run_coding, run_coding_nonpo
from app.agents.risk import run_risk_and_approval
from app.utils.state import update_invoice_status
from app.agents.explain import run_explain
from app.utils.normalize_invoice import ensure_minimal_structure

logger = get_logger(__name__)

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
        logger.info("Orchestrator worker started")


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
            task_id = str(task.get("_id", "unknown"))
            invoice_id = task.get("invoice_id", "unknown")
            logger.info("[task_id=%s invoice_id=%s] Claimed task type=%s", task_id, invoice_id, task.get("type"))
            await process_task(task)
        except Exception:
            # log and sleep
            logger.exception("Orchestrator loop error")
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
        logger.exception("Failed to persist ExplainAgent step for invoice %s", invoice_id)


def _safe_run_explain_and_persist(db, invoice_id: str, invoice_snapshot: dict, trigger_step: dict, validation_result: Optional[dict] = None) -> bool:
    """
    Run run_explain synchronously and persist either the explain step or an error step
    into the invoice workflow so failures are visible (especially in prod).
    
    Args:
        db: MongoDB client
        invoice_id: Invoice ID
        invoice_snapshot: Invoice document snapshot
        trigger_step: Triggering step (e.g., POMatchingAgent output)
        validation_result: Optional ValidationResult dict from invoice.validation (NEW in Step G)
    """
    try:
        # Step G: Pass validation_result to ExplainAgent for grounding
        explain_resp = run_explain(db, invoice_snapshot, trigger_step, validation_result=validation_result)
        if isinstance(explain_resp, dict):
            if "timestamp" not in explain_resp:
                explain_resp["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
            db.invoices.update_one({"_id": invoice_id}, {"$push": {"_workflow.steps": explain_resp}})
            return True
        else:
            logger.error("run_explain returned non-dict for invoice %s: %s", invoice_id, type(explain_resp))
    except Exception as e:
        logger.exception("ExplainAgent failed for invoice %s: %s", invoice_id, str(e))
        err_step = {
            "agent": "ExplainAgent",
            "invoice_id": invoice_id,
            "status": "failed",
            "result": {"error": str(e)},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
        try:
            db.invoices.update_one({"_id": invoice_id}, {"$push": {"_workflow.steps": err_step}})
        except Exception:
            # Last resort: at least log it
            logger.exception("Failed to persist ExplainAgent error step for invoice %s", invoice_id)
    return False


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
        task_id = str(task.get("_id", "unknown"))
        if not invoice_id:
            logger.warning("[task_id=%s] Missing invoice_id in task", task_id)
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "missing_invoice_id"}})
            return

        logger.info("[task_id=%s invoice_id=%s] Starting invoice processing", task_id, invoice_id)
        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
        # normalize invoice to ensure consistent lines/items structure
        invoice = ensure_minimal_structure(invoice)
        if not invoice:
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "error", "error": "invoice_not_found"}})
            return

        # Track if we created a human task (then we will not auto-finalize)
        human_task_created = False

        # --- 1) Validation ---
        logger.info("[task_id=%s invoice_id=%s] Running ValidationAgent", task_id, invoice_id)
        validation_out = await asyncio.to_thread(run_validation, db, invoice)

        # persist validation output into invoice document under _workflow.steps
        await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": validation_out}})

        # Extract and persist structured ValidationResult to invoice.validation
        validation_result = validation_out.get("validation")
        if validation_result:
            await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$set": {"validation": validation_result}})
            logger.info("[task_id=%s invoice_id=%s] ValidationResult persisted: status=%s", task_id, invoice_id, validation_result.get("status"))

        # === STEP D: ORCHESTRATOR BRANCHING ON VALIDATION RESULT STATUS ===
        # Branch explicitly based on ValidationResult.status (PASS / WARN / FAIL)
        validation_status = validation_result.get("status") if validation_result else "UNKNOWN"
        
        if validation_status == "FAIL":
            # FAIL: Stop orchestration immediately, move to EXCEPTION state
            logger.info("[task_id=%s invoice_id=%s] ValidationResult.status=FAIL: Stopping orchestration", task_id, invoice_id)
            await asyncio.to_thread(update_invoice_status, db, invoice_id, "EXCEPTION", "Orchestrator", note="Validation failed - hard blocking issues detected")
            
            # Finish the original task
            now = datetime.datetime.utcnow().isoformat() + "Z"
            await asyncio.to_thread(db.tasks.update_one, {"_id": task["_id"]}, {"$set": {"status": "done", "finished_at": now}})
            
            # Do NOT invoke MatchingAgent or any downstream agents
            return
        
        elif validation_status == "WARN":
            # WARN: Continue to MatchingAgent but retain warnings in persisted data
            logger.info("[task_id=%s invoice_id=%s] ValidationResult.status=WARN: Continuing with warnings", task_id, invoice_id)
            # Set VALIDATED status but mark with warning note
            await asyncio.to_thread(update_invoice_status, db, invoice_id, "VALIDATED", "Orchestrator", note="Validation passed with warnings")
            # Continue to downstream agents (MatchingAgent, CodingAgent, etc.)
        
        elif validation_status == "PASS":
            # PASS: Continue normally to MatchingAgent and downstream
            logger.info("[task_id=%s invoice_id=%s] ValidationResult.status=PASS: Proceeding normally", task_id, invoice_id)
            await asyncio.to_thread(update_invoice_status, db, invoice_id, "VALIDATED", "Orchestrator", note="Validation passed")
            # Continue to downstream agents (MatchingAgent, CodingAgent, etc.)
        
        else:
            # Unknown status - log and continue cautiously
            logger.warning("[task_id=%s invoice_id=%s] Unknown ValidationResult.status=%s: Treating as PASS", task_id, invoice_id, validation_status)
            await asyncio.to_thread(update_invoice_status, db, invoice_id, "VALIDATED", "Orchestrator", note="Validation passed (status unknown)")
            # Continue to downstream agents

        # --- 2) PO Matching (only if validated) ---
        # re-fetch invoice in case validation added fields
        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
        invoice = ensure_minimal_structure(invoice)
        header = invoice.get("header", {}) if invoice else {}
        po_number = header.get("po_number") or header.get("po") or header.get("po_reference")

        if po_number:
            logger.info("[task_id=%s invoice_id=%s] Running POMatchingAgent for PO=%s", task_id, invoice_id, po_number)
            po_out = await asyncio.to_thread(run_po_matching, db, invoice)

            # persist PO matching result into workflow
            await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": po_out}})

            # set status via helper
            matched_status = "MATCHED" if po_out.get("status") == "matched" else "EXCEPTION"
            logger.info("[task_id=%s invoice_id=%s] POMatchingAgent completed: status=%s", task_id, invoice_id, matched_status)
            await asyncio.to_thread(update_invoice_status, db, invoice_id, matched_status, "Orchestrator", note="PO matching result applied")

            # If PO matching produced issues (partial_match), create a human_review task
            if po_out.get("status") != "matched":
                # BEFORE creating the human task for PO mismatch, run ExplainAgent and persist success or failure
                # Step G: Pass validation_result if available
                validation_result = invoice.get("validation") if invoice else None
                await asyncio.to_thread(_safe_run_explain_and_persist, db, invoice_id, invoice, po_out, validation_result)

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
                logger.info("[task_id=%s invoice_id=%s] Running CodingAgent", task_id, invoice_id)
                coding_out = await asyncio.to_thread(run_coding, db, invoice)
                # persist coding agent output to workflow
                await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": coding_out}})

                coding_status = coding_out.get("status")
                logger.info("[task_id=%s invoice_id=%s] CodingAgent completed: status=%s", task_id, invoice_id, coding_status)
                if coding_status in ("completed", "partial"):
                    # For PO-matched invoices: treat both "completed" and "partial" as non-blocking
                    # "partial" means GL coding couldn't be fully determined, but PO already matched
                    # This is acceptable - proceed to Risk & Approval for final decision
                    # mark CODED (uses centralized state helper)
                    await asyncio.to_thread(update_invoice_status, db, invoice_id, "CODED", "Orchestrator", note="Coding applied (PO-matched invoice)")

                    # --- 4) RISK & APPROVAL (run after CODED) ---
                    try:
                        logger.info("[task_id=%s invoice_id=%s] Running RiskApprovalAgent", task_id, invoice_id)
                        invoice = await asyncio.to_thread(db.invoices.find_one, {"_id": invoice_id})
                        risk_out = await asyncio.to_thread(run_risk_and_approval, db, invoice)
                        # persist risk output
                        await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": risk_out}})

                        risk_decision = risk_out.get("decision", risk_out.get("status", "unknown"))
                        logger.info("[task_id=%s invoice_id=%s] RiskApprovalAgent completed: decision=%s", task_id, invoice_id, risk_decision)

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
                elif coding_status == "failed":
                    # Only create human task if coding actually failed (not just partial)
                    now = datetime.datetime.utcnow().isoformat() + "Z"
                    human_task = {
                        "type": "human_review",
                        "invoice_id": invoice_id,
                        "status": "pending",
                        "created_at": now,
                        "payload": {
                            "agent": coding_out.get("agent", "CodingAgent"),
                            "agent_result": coding_out.get("result", coding_out),
                            "reason": "coding_failed"
                        }
                    }
                    await asyncio.to_thread(db.tasks.insert_one, human_task)
                    human_task_created = True
                    # set invoice to EXCEPTION
                    await asyncio.to_thread(update_invoice_status, db, invoice_id, "EXCEPTION", "Orchestrator", note="Coding failed - human review created")
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

        else:
            # --- NON-PO INVOICE: Run CodingAgent with static rules ---
            # For non-PO invoices, we run the deterministic coding agent that uses
            # static JSON rules to assign GL accounts based on vendor name.
            logger.info("[task_id=%s invoice_id=%s] Running CodingAgent (non-PO) for invoice without PO", task_id, invoice_id)
            try:
                coding_out = await asyncio.to_thread(run_coding_nonpo, db, invoice)
                # persist coding agent output to workflow
                await asyncio.to_thread(db.invoices.update_one, {"_id": invoice_id}, {"$push": {"_workflow.steps": coding_out}})

                coding_status = coding_out.get("status")
                logger.info("[task_id=%s invoice_id=%s] CodingAgent (non-PO) completed: status=%s", task_id, invoice_id, coding_status)

                # For non-PO invoices, we mark as CODED if coding completed (even if no rule matched)
                # The invoice will still proceed to READY_FOR_POSTING
                if coding_status == "completed":
                    await asyncio.to_thread(update_invoice_status, db, invoice_id, "CODED", "Orchestrator", note="Non-PO coding applied")
                elif coding_status == "failed":
                    # Only create human task if coding actually failed (not just no match)
                    now = datetime.datetime.utcnow().isoformat() + "Z"
                    human_task = {
                        "type": "human_review",
                        "invoice_id": invoice_id,
                        "status": "pending",
                        "created_at": now,
                        "payload": {
                            "agent": coding_out.get("agent", "CodingAgent"),
                            "agent_result": coding_out.get("result", coding_out),
                            "reason": "coding_failed"
                        }
                    }
                    await asyncio.to_thread(db.tasks.insert_one, human_task)
                    human_task_created = True
                    await asyncio.to_thread(update_invoice_status, db, invoice_id, "EXCEPTION", "Orchestrator", note="Non-PO coding failed - human review created")
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
                logger.error("[task_id=%s invoice_id=%s] CodingAgent (non-PO) failed with error: %s", task_id, invoice_id, e)
                # continue — do not block overall pipeline

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
        logger.info("[task_id=%s invoice_id=%s] Task completed successfully", task_id, invoice_id)
        return

    except Exception as e:
        logger.exception("[task_id=%s invoice_id=%s] Task failed with error", task_id, invoice_id)
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
