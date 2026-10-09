"""Reward router — API_CONTRACT §15 (off-chain)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.reward.service import RewardService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/rewards", tags=["reward"])


@router.get("/me")
def me(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return RewardService.me(db, user.id)


@router.get("/rules")
def rules():
    return {
        "rules": [
            {"name": "outcome_reward", "description": "Rewards follow useful outcomes only [PRD]", "base_units": 10},
            {"name": "engagement", "description": "Messages/views/likes NEVER generate rewards [PRD]", "base_units": 0},
        ]
    }
