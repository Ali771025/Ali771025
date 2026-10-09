"""Conversation Core — orchestrates the MVP loop (API_CONTRACT §16.1 [normative]).

message → intent → personal context → service match → permission → runtime
        → outcome → (reputation/reward hooks) → response + trace
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.conversation.models import Conversation, InvocationTrace, Message
from app.shared.errors import FORBIDDEN, NOT_FOUND, AppError


class ConversationService:
    # ---------- CRUD ----------
    @staticmethod
    def create(db: Session, user_id: int) -> Conversation:
        c = Conversation(user_id=user_id)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c

    @staticmethod
    def list_for(db: Session, user_id: int) -> list[Conversation]:
        return list(db.scalars(select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc())).all())

    @staticmethod
    def get(db: Session, user_id: int, conv_id: int) -> Conversation:
        c = db.get(Conversation, conv_id)
        if not c or c.user_id != user_id:
            raise AppError(NOT_FOUND, "Conversation not found", 404)
        return c

    @staticmethod
    def messages(db: Session, conv_id: int) -> list[Message]:
        return list(db.scalars(select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)).all())

    @staticmethod
    def traces(db: Session, conv_id: int) -> list[InvocationTrace]:
        return list(db.scalars(select(InvocationTrace).where(InvocationTrace.conversation_id == conv_id).order_by(InvocationTrace.started_at.desc())).all())

    # ---------- the loop ----------
    @staticmethod
    def send_message(db: Session, user_id: int, conv_id: int, content: str) -> dict:
        from app.modules.intent.service import IntentService
        from app.modules.outcome.service import OutcomeService
        from app.modules.permission.service import PermissionService
        from app.modules.personal_qora.service import PersonalQoraService
        from app.modules.runtime.service import RuntimeService
        from app.modules.service.service import ServiceRegistry

        conv = ConversationService.get(db, user_id, conv_id)
        now = datetime.now(timezone.utc)

        user_msg = Message(conversation_id=conv.id, role="user", content=content)
        db.add(user_msg)
        db.flush()

        trace = InvocationTrace(conversation_id=conv.id, message_id=user_msg.id)
        db.add(trace)
        db.flush()

        # 1. intent [PRD]
        intent = IntentService.analyze(db, user_id, content, conversation_id=conv.id)
        trace.intent_slug = intent.primary_intent
        trace.intent_confidence = intent.confidence
        trace.entities = intent.entities

        # 2. personal context — least-context privilege [PRD]
        #    capability "career"-like mapping: interview → career, trip → travel …
        needed_types = []
        if "interview_coaching" in intent.required_capabilities:
            needed_types.append("career")
        if "itinerary_planning" in intent.required_capabilities:
            needed_types.append("travel")
        if "english_practice" in intent.required_capabilities:
            needed_types.append("language")

        # 3. service match (discovery ranking) [PRD signals]
        candidates = ServiceRegistry.match_for_intent(db, user_id, intent.primary_intent, limit=3)
        trace.candidate_services = [
            {"service_id": c["service"].id, "score": c["rank"]["score"], "name": c["service"].name}
            for c in candidates
        ]
        chosen = candidates[0] if candidates else None

        # 4. permission gate [PRD hard rule]
        if chosen and needed_types:
            allowed_scopes, missing = PermissionService.resolve(db, user_id, chosen["service"].id, needed_types)
            trace.permission_needed = missing
            if missing:
                conv.recovery_state = "awaiting_permission"
                conv.active_service_id = chosen["service"].id
                trace.finished_at = datetime.now(timezone.utc)
                reply = (
                    f"To run **{chosen['service'].name}** I need permission to use your "
                    + " and ".join(missing)
                    + " context. It is shared only with this service — you can allow once, always allow, or deny."
                )
                out_msg = Message(conversation_id=conv.id, role="assistant", content=reply, content_blocks={
                    "permission_request": {
                        "service_id": chosen["service"].id,
                        "context_types": missing,
                        "mode_options": ["ALLOW_ONCE", "ALWAYS_ALLOW", "DENY"],
                    },
                    "suggestions": ConversationService._suggestions(candidates),
                })
                db.add(out_msg)
                db.commit()
                return ConversationService._response(conv, user_msg, out_msg, intent, trace, chosen, None, None, None)

        granted = PersonalQoraService.resolve_context(db, user_id, needed_types) if needed_types else {}
        trace.context_shared = {k: bool(v) for k, v in granted.items()}

        # 5. direct QORA answer when nothing matches (Personal AI) [PRD]
        if not chosen:
            reply = (
                "I can help with that directly. Based on what I know about you: "
                if granted else
                "Let's work on that together. "
            )
            reply += (
                "Tell me a bit more about the outcome you want, or explore the service network "
                "— I may find a specialist for this."
            )
            out_msg = Message(conversation_id=conv.id, role="assistant", content=reply, content_blocks={
                "suggestions": ConversationService._suggestions(
                    ServiceRegistry.match_for_intent(db, user_id, intent.primary_intent, limit=3)
                ),
            })
            db.add(out_msg)
            trace.finished_at = datetime.now(timezone.utc)
            db.commit()
            return ConversationService._response(conv, user_msg, out_msg, intent, trace, None, None, None, None)

        # 6. runtime execution
        svc = chosen["service"]
        version = ServiceRegistry.get_version(db, svc.current_version_id) if svc.current_version_id else None
        if not version:
            raise AppError(NOT_FOUND, "Service has no runnable version", 404)
        session = RuntimeService.start_session(db, user_id, svc.id, version.id, conv.id)
        run = RuntimeService.execute(
            db, session, version, svc.name, content, granted, intent.entities,
        )

        # 7. outcome evaluation [PRD North Star]
        outcome = OutcomeService.evaluate(db, session, version, run)

        # 8. reputation + reward hooks (event stubs — engines land in Phase 3/5)
        from app.modules.reputation.service import ReputationService
        from app.modules.reward.service import RewardService

        ReputationService.apply_outcome_event(db, svc.creator_id, svc.id, outcome.status)
        RewardService.process_outcome(db, user_id, session.id, outcome.status, outcome.score)
        from app.modules.profile.service import ProfileService as _PS

        _creator = _PS.get_creator_by_id(db, svc.creator_id)
        if _creator:  # creators earn from useful outcomes too [PRD]
            RewardService.process_outcome(db, _creator.user_id, session.id, outcome.status, outcome.score)

        # 9. journey + memory capture (Personal QORA learns) [PRD]
        if intent.primary_intent in ("job_interview_preparation", "trip_planning", "startup_idea_validation"):
            PersonalQoraService.touch_journey(db, user_id, intent.primary_intent, {
                "step": "session_completed" if run.get("ok") else "service_failed",
                "service": svc.name,
            })
        if intent.entities.get("Role"):
            PersonalQoraService.add_memory(
                db, user_id,
                {"kind": "goal", "subject": f"Target role: {intent.entities['Role']}",
                 "content": f"Preparing for a {intent.entities['Role']} opportunity", "sensitivity": "private", "share_policy": "ask"},
                source="inferred", confidence=intent.confidence,
            )

        conv.recovery_state = "service_failed" if not run.get("ok") else "normal"
        conv.active_service_id = svc.id
        trace.chosen_service_id = svc.id
        trace.chosen_service_version_id = version.id
        trace.session_id = session.id
        trace.outcome_status = outcome.status
        trace.finished_at = datetime.now(timezone.utc)

        if run.get("ok"):
            content_blocks = {
                "suggestions": ConversationService._suggestions(candidates),
                "outcome": {"status": outcome.status, "score": outcome.score, "session_id": session.id, "user_confirmation_required": True},
                "deliverable": run.get("deliverable"),
            }
            reply = run["content"]
        else:
            failure = run["failure"]
            content_blocks = {
                "recovery": failure,
                "suggestions": ConversationService._suggestions(candidates),
            }
            reply = (
                f"The service could not complete ({failure['failure_type'].lower().replace('_', ' ')}). "
                "You can continue with QORA directly, or try another service."
            )

        out_msg = Message(conversation_id=conv.id, role="assistant", content=reply, content_blocks=content_blocks)
        db.add(out_msg)
        db.commit()
        return ConversationService._response(conv, user_msg, out_msg, intent, trace, chosen, run, outcome, session)

    # ---------- recovery choice (prototype UX) [PRD] ----------
    @staticmethod
    def recover(db: Session, user_id: int, conv_id: int, option: str) -> dict:
        conv = ConversationService.get(db, user_id, conv_id)
        if option in ("continue_with_qora", "stop"):
            conv.recovery_state = "normal"
            reply = "Continuing with QORA directly — what outcome do you want to reach?" if option == "continue_with_qora" else "Okay, stopping here. I'm ready when you are."
        elif option == "try_another_service":
            conv.recovery_state = "normal"
            reply = "Sure — browse the service network, or describe your need and I'll match another specialist."
        else:  # retry
            reply = "Retrying — resend your last message and I'll run the service again."
        from app.modules.conversation.schemas import MessageOut as _MessageOut

        out_msg = Message(conversation_id=conv.id, role="assistant", content=reply, content_blocks={"suggestions": []})
        db.add(out_msg)
        db.commit()
        return {"message": _MessageOut.model_validate(out_msg).model_dump(), "recovery_state": conv.recovery_state}

    # ---------- helpers ----------
    @staticmethod
    def _suggestions(candidates: list[dict]) -> list[dict]:
        return [
            {
                "service_id": c["service"].id,
                "title": c["service"].name,
                "summary": c["service"].summary,
                "score": c["rank"]["score"],
                "outcome": c["outcome"],
                "followed": c["followed"],
            }
            for c in candidates
        ]

    @staticmethod
    def _response(conv, user_msg, out_msg, intent, trace, chosen, run, outcome, session) -> dict:
        return {
            "conversation_id": conv.id,
            "message": {
                "id": out_msg.id,
                "role": out_msg.role,
                "content": out_msg.content,
                "content_blocks": out_msg.content_blocks,
                "created_at": out_msg.created_at,
            },
            "intent": intent.model_dump(),
            "service_match": {
                "chosen_service_id": chosen["service"].id if chosen else None,
                "candidates": trace.candidate_services,
            },
            "context_shared": trace.context_shared,
            "service_response": {
                "ok": bool(run and run.get("ok")),
                "deliverable": (run or {}).get("deliverable") if run else None,
                "session_id": (run or {}).get("session_id") if run else None,
            },
            "outcome": {
                "status": outcome.status,
                "score": outcome.score,
                "session_id": session.id,
                "user_confirmation_required": True,
            } if outcome else None,
            "trace_id": trace.id,
            "recovery": (run or {}).get("failure") if run and not run.get("ok") else None,
        }
