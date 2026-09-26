"""
Pairing management API for the Hermes dashboard plugin.

Exposes three endpoints mounted at /api/plugins/pairing/:
  GET  /list      — list pending requests and approved users
  POST /approve   — approve a pending request by its request id, or by the
                    pairing code the user reports
  POST /revoke    — revoke an approved user

hermes never hands out the code of a pending request, only its request id,
so the dashboard approves by request id.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway.pairing import PairingStore

router = APIRouter()
_store = PairingStore()


@router.get("/list")
async def list_pairing():
    """Return all pending pairing requests and approved users."""
    return {
        "pending": _store.list_pending(),
        "approved": _store.list_approved(),
    }


class ApproveRequest(BaseModel):
    platform: str
    request_id: str | None = None
    code: str | None = None


@router.post("/approve")
async def approve_pairing(req: ApproveRequest):
    """Approve a pending request and add its user to the approved list."""
    platform = req.platform.lower().strip()
    if req.request_id:
        result = _store.approve_request(platform, req.request_id)
        error = "Request not found or expired"
    elif req.code:
        result = _store.approve_code(platform, req.code)
        error = "Code not found or expired"
    else:
        raise HTTPException(status_code=400, detail="request_id or code is required")
    if result:
        return {
            "ok": True,
            "user_id": result["user_id"],
            "user_name": result.get("user_name", ""),
        }
    return {"ok": False, "error": error}


class RevokeRequest(BaseModel):
    platform: str
    user_id: str


@router.post("/revoke")
async def revoke_pairing(req: RevokeRequest):
    """Revoke an approved user's access."""
    ok = _store.revoke(req.platform.lower().strip(), req.user_id.strip())
    return {"ok": ok}
