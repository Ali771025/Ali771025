"""Module registry — explicit APIRouter imports (registration order preserved)."""
# Skeleton modules define `router` inside their package __init__
from app.modules.analytics.router import router as analytics
from app.modules.knowledge.router import router as knowledge

# Feature modules expose `router` in router.py — import the OBJECT, not the submodule
from app.modules.conversation.router import router as conversation
from app.modules.creator.router import router as creator
from app.modules.identity.router import me as identity_me
from app.modules.identity.router import router as identity
from app.modules.intent.router import router as intent
from app.modules.outcome.router import router as outcome
from app.modules.permission.router import router as permission
from app.modules.personal_qora.router import router as personal_qora
from app.modules.profile.router import router as profile
from app.modules.qualification.router import router as qualification
from app.modules.reputation.router import router as reputation
from app.modules.reward.router import router as reward
from app.modules.runtime.router import router as runtime
from app.modules.service.router import router as service

ROUTERS = [
    identity,
    identity_me,
    profile,
    personal_qora,
    permission,
    intent,
    service,
    runtime,
    conversation,
    outcome,
    knowledge,
    creator,
    qualification,
    reputation,
    analytics,
    reward,
]
