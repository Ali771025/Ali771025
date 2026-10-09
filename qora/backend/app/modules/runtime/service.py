"""Service Runtime v2 — policy gates, trusted tools, model fallback, and audit events."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.runtime.gateway import ModelGateway
from app.modules.runtime.models import FailureEvent, ModelCall, ServiceSession, SessionEvent, ToolInvocation
from app.shared.errors import POLICY_BLOCK, AppError

# Failure taxonomy (ARCHITECTURE §4.28)
FAILURES = [
    "MODEL_FAILURE", "TOOL_FAILURE", "MISSING_CONTEXT", "PERMISSION_DENIED",
    "KNOWLEDGE_FAILURE", "SERVICE_UNAVAILABLE", "POLICY_BLOCK", "TIMEOUT", "LOW_CONFIDENCE",
]
RECOVERY_BY_FAILURE = {
    "MODEL_FAILURE": "fallback_service",
    "TOOL_FAILURE": "fallback_service",
    "MISSING_CONTEXT": "ask_user",
    "PERMISSION_DENIED": "ask_user",
    "KNOWLEDGE_FAILURE": "fallback_service",
    "SERVICE_UNAVAILABLE": "fallback_service",
    "POLICY_BLOCK": "stop",
    "TIMEOUT": "fallback_model",
    "LOW_CONFIDENCE": "ask_user",
}


def _event(db: Session, session_id: int, kind: str, payload: dict):
    db.add(SessionEvent(session_id=session_id, kind=kind, payload=payload))


class RuntimeService:
    @staticmethod
    def start_session(db: Session, user_id: int, service_id: int, version_id: int, conversation_id: int | None) -> ServiceSession:
        session = ServiceSession(
            user_id=user_id,
            service_id=service_id,
            service_version_id=version_id,
            conversation_id=conversation_id,
            status="running",
        )
        db.add(session)
        db.flush()
        _event(db, session.id, "session_started", {"service_id": service_id})
        return session

    @staticmethod
    def record_event(db: Session, session_id: int, kind: str, payload: dict) -> SessionEvent:
        """Internal event-pipeline interface; selected signal kinds are upserted on replay."""
        if kind in ("outcome_confirmation", "unmet_request"):
            existing = db.scalar(
                select(SessionEvent)
                .where(SessionEvent.session_id == session_id, SessionEvent.kind == kind)
                .order_by(SessionEvent.id.desc())
            )
            if existing:
                existing.payload = payload
                return existing
        row = SessionEvent(session_id=session_id, kind=kind, payload=payload)
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def clear_event(db: Session, session_id: int, kind: str) -> None:
        """Deactivate a revisable feedback signal without deleting the audit history."""
        row = db.scalar(
            select(SessionEvent)
            .where(SessionEvent.session_id == session_id, SessionEvent.kind == kind)
            .order_by(SessionEvent.id.desc())
        )
        if row:
            row.payload = {**(row.payload or {}), "active": False}
            db.flush()

    @staticmethod
    def execute(
        db: Session,
        session: ServiceSession,
        version,
        service_name: str,
        user_message: str,
        granted_context: dict,
        entities: dict,
    ) -> dict:
        """Runs the protected pipeline; failures are recorded and returned, not raised."""
        from app.modules.profile.service import ProfileService
        from app.modules.service.risk import RiskService
        from app.modules.service.service import ServiceRegistry

        try:
            service = ServiceRegistry.get(db, session.service_id)
            creator = ProfileService.get_creator_by_id(db, service.creator_id)
            allowed, reason = RiskService.runtime_gate(service, creator, version)
            if not allowed:
                _event(db, session.id, "guardrail", {"blocked": "risk_gate", "risk_level": service.risk_level})
                return RuntimeService._fail(db, session, "POLICY_BLOCK", "stop", reason or "Risk policy blocked this service")

            # Knowledge is version-bound; stale material lowers trust and rank before serving.
            knowledge_note = (version.knowledge_config or {}).get("note", "")
            knowledge_chunks: list[str] = []
            knowledge_version_id = (version.knowledge_config or {}).get("knowledge_version_id")
            if knowledge_version_id:
                from app.modules.knowledge.service import KnowledgeService

                knowledge_chunks = KnowledgeService.search(db, int(knowledge_version_id), user_message, k=2)
            _event(db, session.id, "knowledge", {"loaded": bool(knowledge_chunks or knowledge_note), "chunks": len(knowledge_chunks)})

            # Tools can only be selected from the service version's declared allow-list.
            tool_results: dict[str, dict] = {}
            config = version.tools_config or {}
            tool_names = config.get("tools", [])
            arguments_by_tool = config.get("arguments", {})
            if isinstance(tool_names, dict):
                arguments_by_tool = {**arguments_by_tool, **tool_names}
                tool_names = list(tool_names)
            if tool_names:
                from app.modules.runtime.tools import ToolService

                for tool_name in tool_names:
                    tool_name = str(tool_name)
                    arguments = arguments_by_tool.get(tool_name, {}) if isinstance(arguments_by_tool, dict) else {}
                    result = ToolService.execute(
                        db,
                        session.id,
                        service.id,
                        tool_name,
                        arguments if isinstance(arguments, dict) else {},
                        granted_context,
                    )
                    if not result.get("ok"):
                        failure_type = "POLICY_BLOCK" if result.get("status") == "denied" else "TOOL_FAILURE"
                        action = "stop" if failure_type == "POLICY_BLOCK" else "fallback_service"
                        return RuntimeService._fail(db, session, failure_type, action, result.get("error", "Tool failed"))
                    tool_results[tool_name] = result.get("result", {})

            system = version.system_instructions or f"You are {service_name}. Purpose: {version.purpose}"
            if knowledge_chunks:
                system += "\n\nRelevant training material:\n" + "\n---\n".join(knowledge_chunks)
            if knowledge_note:
                system += "\n\nService note:\n" + str(knowledge_note)[:1200]
            if tool_results:
                system += "\n\nValidated tool results:\n" + str(tool_results)[:2000]

            try:
                result = ModelGateway.invoke_with_fallback(
                    system,
                    user_message,
                    needs=version.model_requirements or {},
                    context={
                        "service_name": service_name,
                        "purpose": version.purpose,
                        "entities": entities,
                        "granted_context": granted_context,
                    },
                )
            except Exception as exc:
                message = str(exc)
                failure_type = "TIMEOUT" if "timeout" in message.lower() else "MODEL_FAILURE"
                return RuntimeService._fail(
                    db, session, failure_type, RECOVERY_BY_FAILURE[failure_type], message
                )

            if result.get("fallback_used"):
                _event(db, session.id, "fallback_model", {
                    "provider": result.get("provider"),
                    "reason": result.get("fallback_reason", "primary unavailable"),
                })
            db.add(ModelCall(
                session_id=session.id,
                provider=result["provider"],
                model=result["model"],
                prompt_tokens=result.get("prompt_tokens", 0),
                completion_tokens=result.get("completion_tokens", 0),
                latency_ms=result.get("latency_ms", 0),
                cost_usd=result.get("cost_usd", 0.0),
            ))

            # Basic output safety gate; never retry or route around a policy block.
            blocked_words = ["i will hack", "malware", "bypass security"]
            content = result.get("content") or ""
            if any(word in content.lower() for word in blocked_words):
                _event(db, session.id, "guardrail", {"blocked": "output_policy"})
                from app.modules.reputation.service import ReputationService

                ReputationService.apply_safety_failure(db, service.id, session.id, "output_policy")
                return RuntimeService._fail(db, session, "POLICY_BLOCK", "stop", "Output policy violation")

            session.status = "completed"
            session.finished_at = datetime.now(timezone.utc)
            session.context_shared = granted_context
            _event(db, session.id, "response", {"ok": True, "fallback_model": bool(result.get("fallback_used"))})
            db.commit()
            return {
                "ok": True,
                "content": content,
                "deliverable": result.get("deliverable"),
                "session_id": session.id,
                "provider": result.get("provider"),
                "fallback_model": bool(result.get("fallback_used")),
                "failure": None,
            }

        except AppError:
            raise
        except Exception as exc:
            return RuntimeService._fail(db, session, "SERVICE_UNAVAILABLE", "fallback_service", str(exc))

    @staticmethod
    def _fail(db: Session, session: ServiceSession, failure_type: str, recovery: str, detail: str) -> dict:
        session.status = "failed"
        session.finished_at = datetime.now(timezone.utc)
        db.add(FailureEvent(
            session_id=session.id,
            failure_type=failure_type,
            recovery_action=recovery,
            detail=detail[:2000],
        ))
        _event(db, session.id, "recovery", {
            "failure_type": failure_type,
            "recovery_action": recovery,
        })
        db.commit()
        options = ["stop"] if failure_type == "POLICY_BLOCK" else ["continue_with_qora", "try_another_service", "retry", "stop"]
        return {
            "ok": False,
            "content": None,
            "deliverable": None,
            "session_id": session.id,
            "failure": {
                "failure_type": failure_type,
                "recovery_action": recovery,
                "options": options,
                "detail": detail[:200],
            },
        }

    @staticmethod
    def sessions_for_service(db: Session, service_id: int) -> list[dict]:
        """Service-layer interface for analytics and repeat-use scoring."""
        rows = db.scalars(select(ServiceSession).where(ServiceSession.service_id == service_id)).all()
        return [
            {
                "session_id": row.id,
                "user_id": row.user_id,
                "status": row.status,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
            }
            for row in rows
        ]

    @staticmethod
    def session_events_for_service(
        db: Session,
        service_id: int,
        kind: str | None = None,
        since: datetime | None = None,
    ) -> list[dict]:
        query = (
            select(SessionEvent, ServiceSession)
            .join(ServiceSession, ServiceSession.id == SessionEvent.session_id)
            .where(ServiceSession.service_id == service_id)
            .order_by(SessionEvent.occurred_at)
        )
        if kind:
            query = query.where(SessionEvent.kind == kind)
        if since:
            query = query.where(SessionEvent.occurred_at >= since)
        return [
            {
                "session_id": event.session_id,
                "kind": event.kind,
                "payload": event.payload or {},
                "at": event.occurred_at,
            }
            for event, _session in db.execute(query).all()
        ]

    @staticmethod
    def session_events(db: Session, session_id: int) -> list[dict]:
        rows = db.scalars(
            select(SessionEvent)
            .where(SessionEvent.session_id == session_id)
            .order_by(SessionEvent.occurred_at)
        ).all()
        return [
            {"kind": row.kind, "payload": row.payload, "at": row.occurred_at}
            for row in rows
        ]
