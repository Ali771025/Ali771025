"""Analytics — Phase 4: event pipeline → creator metrics → AI insights.

Phase 0/1 state: skeleton router.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/_status")
def status():
    return {
        "module": "analytics",
        "phase": "skeleton",
        "planned": ["event pipeline", "creator metrics", "AI creator insights", "knowledge gap detection"],
    }
