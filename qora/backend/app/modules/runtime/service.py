"""Service Runtime v1 — the critical path (ARCHITECTURE §4.11).

Pipeline: load version → policy → context resolve → permission check → knowledge (stub)
→ tools (stub) → model call → guardrails → response → (outcome hook lives in conversation).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.runtime.gateway import ModelGateway
from app.modules.runtime.models import FailureEvent, ModelCall, ServiceSession, SessionEvent, ToolInvocation
from app.shared.errors import POLICY_BLOCK, SERVICE_UNAVAILABLE, AppError

# Failure taxonomy (ARCHITECTURE §4.28)
FAILURES = [
    "MODEL_FAILURE", "TOOL_FAILURE", "MISSING_CONTEXT", "PERMISSION_DENIED",
    "KNOWLEDGE_FAILURE", "SERVICE_UNAVAILABLE", "POLICY_BLOCK", "TIMEOUT", "LOW_CONFIDENCE",
]

RECOVERY_OPTIONS = ["continue_with_qora", "try_another_service", "retry", "stop"]


def _event(db: Session, session_id: int, kind: str, payload: dict):
    db.add(SessionEvent(session_id=session_id, kind=kind, payload=payload))


class RuntimeService:
    @staticmethod
    def start_session(db: Session, user_id: int, service_id: int, version_id: int, conversation_id: int | None) -> ServiceSession:
        s = ServiceSession(user_id=user_id, service_id=service_id, service_version_id=version_id, conversation_id=conversation_id, status="running")
        db.add(s)
        db.flush()
        return s

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
        """Runs the pipeline. Returns run result; failures are recorded, not raised."""
        try:
            # 1. runtime policy — risk gate [PRD: risk-based]
            if getattr(version, "risk_level", "LOW") == "RESTRICTED":
                _event(db, session.id, "guardrail", {"blocked": "restricted_service"})
                return RuntimeService._fail(db, session, "POLICY_BLOCK", "stop", "Restricted service blocked")

            # 2. knowledge load — real retrieval when the version binds a KnowledgeVersion
            knowledge_note = version.knowledge_config.get("note", "") if version.knowledge_config else ""
            kn_chunks: list[str] = []
            kv_id = (version.knowledge_config or {}).get("knowledge_version_id")
            if kv_id:
                from app.modules.knowledge.service import KnowledgeService

                kn_chunks = KnowledgeService.search(db, int(kv_id), user_message, k=2)
            _event(db, session.id, "knowledge", {"loaded": bool(kn_chunks or knowledge_note), "chunks": len(kn_chunks)})

            # 3. tools resolve (stub — Phase 3 brings policy-gated tools)
            tools = version.tools_config.get("tools", []) if version.tools_config else []
            if tools:
                db.add(ToolInvocation(session_id=session.id, tool_name=str(tools[0]), input={}, output={"note": "stub"}, status="ok"))
                _event(db, session.id, "tool_call", {"tool": tools[0], "status": "stub"})

            # 4. model call through the gateway
            system = version.system_instructions or f"You are {service_name}. Purpose: {version.purpose}"
            if kn_chunks:
                system += "\n\nRelevant training material:\n" + "\n---\n".join(kn_chunks)
            try:
                result = ModelGateway.invoke(
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
            except Exception as exc:  # MODEL_FAILURE → graceful recovery [PRD UX]
                return RuntimeService._fail(db, session, "MODEL_FAILURE", "continue_with_qora", str(exc))

            db.add(ModelCall(
                session_id=session.id,
                provider=result["provider"],
                model=result["model"],
                prompt_tokens=result.get("prompt_tokens", 0),
                completion_tokens=result.get("completion_tokens", 0),
                latency_ms=result.get("latency_ms", 0),
                cost_usd=result.get("cost_usd", 0.0),
            ))

            # 5. guardrails on output
            blocked_words = ["i will hack", "malware", "bypass security"]
            low = result["content"].lower()
            if any(w in low for w in blocked_words):
                _event(db, session.id, "guardrail", {"blocked": "output_policy"})
                return RuntimeService._fail(db, session, "POLICY_BLOCK", "stop", "Output policy violation")

            session.status = "completed"
            session.finished_at = datetime.now(timezone.utc)
            session.context_shared = granted_context
            _event(db, session.id, "response", {"ok": True})
            db.commit()
            return {"ok": True, "content": result["content"], "deliverable": result.get("deliverable"), "session_id": session.id, "failure": None}

        except AppError:
            raise
        except Exception as exc:
            return RuntimeService._fail(db, session, "SERVICE_UNAVAILABLE", "retry", str(exc))

    @staticmethod
    def _fail(db: Session, session: ServiceSession, failure_type: str, recovery: str, detail: str) -> dict:
        session.status = "failed"
        session.finished_at = datetime.now(timezone.utc)
        db.add(FailureEvent(session_id=session.id, failure_type=failure_type, recovery_action=recovery, detail=detail[:2000]))
        _event(db, session.id, "recovery", {"failure_type": failure_type, "recovery_action": recovery})
        db.commit()
        return {
            "ok": False,
            "content": None,
            "deliverable": None,
            "session_id": session.id,
            "failure": {
                "failure_type": failure_type,
                "recovery_action": recovery,
                "options": RECOVERY_OPTIONS,
                "detail": detail[:200],
            },
        }

    @staticmethod
    def sessions_for_service(db: Session, service_id: int) -> list[dict]:
        """Interface for analytics (boundary rule)."""
        from sqlalchemy import select

        rows = db.scalars(select(ServiceSession).where(ServiceSession.service_id == service_id)).all()
        return [{"user_id": r.user_id, "status": r.status} for r in rows]

    @staticmethod
    def session_events(db: Session, session_id: int) -> list[dict]:
        from sqlalchemy import select

        rows = db.scalars(select(SessionEvent).where(SessionEvent.session_id == session_id).order_by(SessionEvent.occurred_at)).all()
        return [{"kind": r.kind, "payload": r.payload, "at": r.occurred_at} for r in rows]
