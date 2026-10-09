"""Personal QORA service — memory, goals, journeys, least-context resolver [PRD]."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.personal_qora.models import Goal, Journey, Memory
from app.shared.errors import NOT_FOUND, AppError

# Which memory kinds may feed each context type (least-context privilege) [PRD]
CONTEXT_KIND_MAP = {
    "career": ["profile_fact", "persistent_context", "goal"],
    "goals": ["goal", "journey_state"],
    "preferences": ["preference", "interaction_insight"],
    "travel": ["profile_fact", "temporary_context", "preference"],
    "language": ["persistent_context", "preference"],
}


class PersonalQoraService:
    # ---------- memories ----------
    @staticmethod
    def list_memories(db: Session, user_id: int, kind: str | None = None) -> list[Memory]:
        q = select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc())
        if kind:
            q = q.where(Memory.kind == kind)
        return list(db.scalars(q).all())

    @staticmethod
    def add_memory(db: Session, user_id: int, data: dict, source: str = "user", confidence: float = 1.0) -> Memory:
        m = Memory(user_id=user_id, source=source, confidence=confidence, **data)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m

    @staticmethod
    def update_memory(db: Session, user_id: int, memory_id: int, data: dict) -> Memory:
        m = db.get(Memory, memory_id)
        if not m or m.user_id != user_id or not m.user_editable:
            raise AppError(NOT_FOUND, "Memory not found", 404)
        for k, v in data.items():
            setattr(m, k, v)
        db.commit()
        db.refresh(m)
        return m

    @staticmethod
    def forget(db: Session, user_id: int, memory_id: int):
        m = db.get(Memory, memory_id)
        if not m or m.user_id != user_id:
            raise AppError(NOT_FOUND, "Memory not found", 404)
        db.delete(m)  # right-to-forget [PRD]
        db.commit()

    # ---------- goals / journeys ----------
    @staticmethod
    def list_goals(db: Session, user_id: int) -> list[Goal]:
        return list(db.scalars(select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at.desc())).all())

    @staticmethod
    def add_goal(db: Session, user_id: int, data: dict) -> Goal:
        g = Goal(user_id=user_id, **data)
        db.add(g)
        db.commit()
        db.refresh(g)
        return g

    @staticmethod
    def update_goal(db: Session, user_id: int, goal_id: int, data: dict) -> Goal:
        g = db.get(Goal, goal_id)
        if not g or g.user_id != user_id:
            raise AppError(NOT_FOUND, "Goal not found", 404)
        for k, v in data.items():
            setattr(g, k, v)
        db.commit()
        db.refresh(g)
        return g

    @staticmethod
    def list_journeys(db: Session, user_id: int) -> list[Journey]:
        return list(db.scalars(select(Journey).where(Journey.user_id == user_id).order_by(Journey.updated_at.desc())).all())

    @staticmethod
    def get_journey(db: Session, user_id: int, journey_id: int) -> Journey:
        j = db.get(Journey, journey_id)
        if not j or j.user_id != user_id:
            raise AppError(NOT_FOUND, "Journey not found", 404)
        return j

    @staticmethod
    def touch_journey(db: Session, user_id: int, kind: str, state: dict) -> Journey:
        j = db.scalar(select(Journey).where(Journey.user_id == user_id, Journey.kind == kind))
        if not j:
            j = Journey(user_id=user_id, kind=kind, state=state, history=[])
            db.add(j)
        else:
            hist = list(j.history or [])
            hist.append({"prev_state": j.state, "at": datetime.now(timezone.utc).isoformat()})
            j.state = state
            j.history = hist[-20:]
        db.commit()
        db.refresh(j)
        return j

    # ---------- least-context resolver [PRD] ----------
    @staticmethod
    def resolve_context(db: Session, user_id: int, context_types: list[str]) -> dict:
        """Return the MINIMAL memory-derived context for the requested types only."""
        kinds: set[str] = set()
        for t in context_types:
            kinds.update(CONTEXT_KIND_MAP.get(t, []))
        out: dict[str, list[dict]] = {}
        now = datetime.now(timezone.utc)
        for m in db.scalars(select(Memory).where(Memory.user_id == user_id)).all():
            if m.kind not in kinds:
                continue
            if m.expires_at and m.expires_at.replace(tzinfo=m.expires_at.tzinfo or timezone.utc) < now:
                continue
            if m.sensitivity == "sensitive" and m.share_policy != "allow":
                continue
            if m.share_policy == "deny":
                continue
            out.setdefault(m.kind, []).append({"subject": m.subject, "content": m.content})
        return out

    @staticmethod
    def context_summary(db: Session, user_id: int) -> dict:
        """'My QORA' — what QORA currently understands about the user."""
        memories = PersonalQoraService.list_memories(db, user_id)
        return {
            "memories": [{"kind": m.kind, "subject": m.subject, "content": m.content} for m in memories],
            "goals": [{"title": g.title, "status": g.status} for g in PersonalQoraService.list_goals(db, user_id)],
            "journeys": [{"kind": j.kind, "state": j.state} for j in PersonalQoraService.list_journeys(db, user_id)],
        }
