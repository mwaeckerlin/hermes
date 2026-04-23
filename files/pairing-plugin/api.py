"""
Pairing management API for the Hermes dashboard plugin.

Exposes three endpoints mounted at /api/plugins/pairing/:
  GET  /list      — list pending requests and approved users
  POST /approve   — approve a pending pairing code
  POST /revoke    — revoke an approved user
"""

from fastapi import APIRouter
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
    code: str


@router.post("/approve")
async def approve_pairing(req: ApproveRequest):
    """Approve a pending pairing code and add the user to the approved list."""
    result = _store.approve_code(req.platform.lower().strip(), req.code.upper().strip())
    if result:
        return {
            "ok": True,
            "user_id": result["user_id"],
            "user_name": result.get("user_name", ""),
        }
    return {"ok": False, "error": "Code not found or expired"}


class RevokeRequest(BaseModel):
    platform: str
    user_id: str


@router.post("/revoke")
async def revoke_pairing(req: RevokeRequest):
    """Revoke an approved user's access."""
    ok = _store.revoke(req.platform.lower().strip(), req.user_id.strip())
    return {"ok": ok}
