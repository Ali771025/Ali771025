"""Creator Platform — Phase 2 delivers the full PRD flow.

Flow [PRD]: Intent → Interview → Generate → Simulate → Review → Visibility → Qualify
Phase 0/1 state: skeleton router.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/creator", tags=["creator"])


@router.get("/_status")
def status():
    return {
        "module": "creator",
        "phase": "skeleton",
        "prd_flow": ["intent", "interview", "generate", "simulate", "review", "visibility", "qualify"],
        "philosophy": "Conversation over Configuration [PRD]",
    }
