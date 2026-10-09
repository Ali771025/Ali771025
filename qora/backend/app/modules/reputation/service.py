"""Trust + reputation engines — event-driven, component-based [PRD Phase 3]."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reputation.models import ReputationEvent, ReputationEventKey, TrustScore

EVENT_KINDS = {
    "successful_outcome",
    "confirmed_complaint",
    "repeat_use",
    "quality_update",
    "verification",
    "safety_failure",
    "stale_knowledge",
}
COMPONENT_WEIGHTS = {
    "safety": 0.25,
    "reliability": 0.20,
    "quality": 0.20,
    "freshness": 0.15,
    "satisfaction": 0.10,
    "repeat_use": 0.05,
    "verification": 0.05,
}


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _overall(components: dict) -> float:
    return round(sum(COMPONENT_WEIGHTS[k] * _clamp(components[k]) for k in COMPONENT_WEIGHTS), 4)


class ReputationService:
    @staticmethod
    def apply_event(
        db: Session,
        subject_type: str,
        subject_id: int,
        kind: str,
        *,
        idempotency_key: str | None = None,
        meta: dict | None = None,
        fallback_score: float = 0.5,
    ) -> bool:
        """Apply one of the seven supported events once; returns False on replay."""
        if subject_type not in ("creator", "service") or kind not in EVENT_KINDS:
            raise ValueError("Unsupported reputation subject or event kind")
        if idempotency_key and db.get(ReputationEventKey, idempotency_key):
            return False
        meta = dict(meta or {})
        row = db.scalar(
            select(TrustScore).where(
                TrustScore.subject_type == subject_type,
                TrustScore.subject_id == subject_id,
            )
        )
        base = _clamp(row.overall if row else fallback_score)
        existing = dict(row.components or {}) if row else {}
        components = {key: _clamp(existing.get(key, base)) for key in COMPONENT_WEIGHTS}
        if row is None:
            row = TrustScore(subject_type=subject_type, subject_id=subject_id, overall=base, components=components)
            db.add(row)
            db.flush()

        if kind == "successful_outcome":
            components["reliability"] = _clamp(components["reliability"] + 0.01)
            components["quality"] = _clamp(components["quality"] + 0.015)
        elif kind == "confirmed_complaint":
            components["satisfaction"] = _clamp(components["satisfaction"] - 0.08)
            components["quality"] = _clamp(components["quality"] - 0.05)
            components["reliability"] = _clamp(components["reliability"] - 0.03)
        elif kind == "repeat_use":
            components["repeat_use"] = _clamp(components["repeat_use"] + 0.025)
        elif kind == "quality_update":
            target = meta.get("score")
            if target is not None:
                target = _clamp(float(target))
                components["quality"] = _clamp(0.8 * components["quality"] + 0.2 * target)
                components["reliability"] = _clamp(0.9 * components["reliability"] + 0.1 * target)
            else:
                delta = float(meta.get("delta", 0.0))
                components["quality"] = _clamp(components["quality"] + delta)
            if meta.get("freshness_score") is not None:
                components["freshness"] = _clamp(float(meta["freshness_score"]))
        elif kind == "verification":
            status = meta.get("status", "verified")
            target = 1.0 if status == "verified" else 0.0 if status == "rejected" else 0.5
            components["verification"] = _clamp(0.75 * components["verification"] + 0.25 * target)
        elif kind == "safety_failure":
            # Immediate, intentionally larger penalty [PRD].
            components["safety"] = _clamp(components["safety"] - 0.35)
            components["reliability"] = _clamp(components["reliability"] - 0.05)
        elif kind == "stale_knowledge":
            target = _clamp(float(meta.get("freshness_score", 0.0)))
            components["freshness"] = min(components["freshness"], target)
            components["quality"] = _clamp(components["quality"] - 0.02)

        row.components = components
        row.overall = _overall(components)
        event = ReputationEvent(
            subject_type=subject_type,
            subject_id=subject_id,
            kind=kind,
            delta=round(row.overall - base, 4),
            meta=meta,
        )
        db.add(event)
        db.flush()
        if idempotency_key:
            db.add(ReputationEventKey(idempotency_key=idempotency_key[:180], event_id=event.id))
        if subject_type == "creator":
            from app.modules.profile.service import ProfileService

            creator = ProfileService.get_creator_by_id(db, subject_id)
            if creator:
                creator.trust_score = row.overall
        db.commit()
        return True

    @staticmethod
    def apply_outcome_event(
        db: Session,
        creator_id: int,
        service_id: int,
        outcome_status: str,
        session_id: int | None = None,
        score: float | None = None,
    ) -> None:
        if outcome_status == "SUCCESS":
            kind, meta = "successful_outcome", {"outcome_status": outcome_status}
        elif outcome_status == "UNKNOWN":
            return
        else:
            kind, meta = "quality_update", {
                "outcome_status": outcome_status,
                "score": score if score is not None else (0.55 if outcome_status == "PARTIAL" else 0.1),
            }
        for subject_type, subject_id in (("creator", creator_id), ("service", service_id)):
            key = f"outcome:{session_id}:{subject_type}:{subject_id}" if session_id else None
            ReputationService.apply_event(
                db,
                subject_type,
                subject_id,
                kind,
                idempotency_key=key,
                meta=meta,
                fallback_score=0.5,
            )

    @staticmethod
    def apply_repeat_use(db: Session, creator_id: int, service_id: int, session_id: int) -> None:
        for subject_type, subject_id in (("creator", creator_id), ("service", service_id)):
            ReputationService.apply_event(
                db,
                subject_type,
                subject_id,
                "repeat_use",
                idempotency_key=f"repeat:{session_id}:{subject_type}:{subject_id}",
                meta={"session_id": session_id},
            )

    @staticmethod
    def apply_safety_failure(db: Session, service_id: int, session_id: int, detail: str = "") -> None:
        from app.modules.service.service import ServiceRegistry

        service = ServiceRegistry.get(db, service_id)
        key_base = f"safety:{session_id}"
        ReputationService.apply_event(
            db,
            "service",
            service_id,
            "safety_failure",
            idempotency_key=f"{key_base}:service:{service_id}",
            meta={"session_id": session_id, "detail": detail[:180]},
        )
        ReputationService.apply_event(
            db,
            "creator",
            service.creator_id,
            "safety_failure",
            idempotency_key=f"{key_base}:creator:{service.creator_id}",
            meta={"session_id": session_id, "service_id": service_id},
        )

    @staticmethod
    def apply_stale_knowledge(
        db: Session,
        creator_id: int,
        service_id: int,
        source_fingerprint: str,
        stale_sources: list,
    ) -> None:
        from app.modules.knowledge.service import KnowledgeService
        from app.modules.service.service import ServiceRegistry

        service = ServiceRegistry.get(db, service_id)
        version = ServiceRegistry.current_version(db, service)
        knowledge_id = ((version.knowledge_config or {}).get("knowledge_version_id") if version else None)
        freshness = KnowledgeService.freshness_for_version(db, knowledge_id)
        for subject_type, subject_id in (("service", service_id), ("creator", creator_id)):
            ReputationService.apply_event(
                db,
                subject_type,
                subject_id,
                "stale_knowledge",
                idempotency_key=f"stale:{service_id}:{source_fingerprint}:{subject_type}:{subject_id}",
                meta={
                    "service_id": service_id,
                    "knowledge_version_id": knowledge_id,
                    "stale_sources": stale_sources,
                    "freshness_score": freshness["score"],
                },
                fallback_score=0.5,
            )

    @staticmethod
    def trust_for(db: Session, subject_type: str, subject_id: int, fallback: float = 0.5) -> dict:
        row = db.scalar(
            select(TrustScore).where(
                TrustScore.subject_type == subject_type,
                TrustScore.subject_id == subject_id,
            )
        )
        score = _clamp(row.overall if row else fallback)
        components = dict(row.components or {}) if row else {}
        if not components:
            components = {key: score for key in COMPONENT_WEIGHTS}
        return {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "overall": score,
            "components": components,
        }

    @staticmethod
    def list_events(db: Session, limit: int = 100, kind: str | None = None) -> list[dict]:
        query = select(ReputationEvent).order_by(ReputationEvent.id.desc()).limit(min(max(limit, 1), 250))
        if kind:
            query = query.where(ReputationEvent.kind == kind)
        return [
            {
                "id": row.id,
                "subject_type": row.subject_type,
                "subject_id": row.subject_id,
                "kind": row.kind,
                "delta": row.delta,
                "meta": row.meta or {},
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            }
            for row in db.scalars(query).all()
        ]
