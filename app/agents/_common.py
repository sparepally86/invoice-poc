
from datetime import datetime
from typing import Dict, Any

def ensure_agent_response(agent_name: str, resp: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the agent response contains canonical top-level keys."""
    if resp is None:
        resp = {}
    # canonical keys
    resp.setdefault("agent", agent_name)
    resp.setdefault("status", resp.get("status", "failed"))
    # result key may be called 'result' or 'data' in some code; normalize
    if "result" not in resp and "data" in resp:
        resp["result"] = resp.get("data")
    resp.setdefault("result", resp.get("result", {}))
    resp.setdefault("next_agent", resp.get("next_agent", None))
    resp.setdefault("score", float(resp.get("score", 0.0) or 0.0))
    resp.setdefault("timestamp", resp.get("timestamp", datetime.utcnow().isoformat() + "Z"))
    # keep errors if present
    if "errors" not in resp:
        resp["errors"] = resp.get("errors", [])
    return resp
