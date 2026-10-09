"""Multi-service orchestration — one outcome planned across a bounded service chain [PRD/TECH].

Modules are reached only through their service interfaces, preserving the monolith boundaries.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.orchestrator.models import OrchestrationPlan, OrchestrationStep
from app.shared.errors import CONFLICT, NOT_FOUND, AppError


class OrchestratorService:
    MAX_STEPS = 4

    @staticmethod
    def plan(db: Session, user_id: int, goal_text: str) -> dict:
        from app.modules.intent.service import IntentService
        from app.modules.service.service import ServiceRegistry

        intent = IntentService.analyze(db, user_id, goal_text, None)
        intent_slugs = [intent.primary_intent, *(intent.secondary_intents or [])]
        capabilities = IntentService.capabilities_for_intents(intent_slugs)
        if not capabilities:
            capabilities = list(intent.required_capabilities or [])

        steps: list[dict] = []
        used: set[int] = set()
        for capability in capabilities:
            if len(steps) >= OrchestratorService.MAX_STEPS:
                break
            candidates = ServiceRegistry.by_capability(db, capability, limit=5)
            for item in candidates:
                service = item["service"]
                if service.id in used:
                    continue
                used.add(service.id)
                steps.append({
                    "service_id": service.id,
                    "service_name": service.name,
                    "role": capability,
                    "summary": service.summary,
                })
                break

        if not steps:
            raise AppError(NOT_FOUND, "No published services can safely help with this goal", 404)

        plan_row = OrchestrationPlan(
            user_id=user_id,
            goal_text=goal_text.strip(),
            intent_slug=intent.primary_intent,
            status="draft",
            summary=f"{len(steps)} service step(s) are ready for your review.",
        )
        db.add(plan_row)
        db.flush()
        for order, step in enumerate(steps, start=1):
            db.add(OrchestrationStep(
                plan_id=plan_row.id,
                step_order=order,
                service_id=step["service_id"],
                service_name=step["service_name"],
                role=step["role"],
                output={"hint": step["summary"]},
            ))
        from app.shared.audit import record

        record(db, user_id, "orchestration.plan.created", plan_row.id, {
            "intent": intent.primary_intent,
            "steps": [step["service_id"] for step in steps],
        })
        db.commit()
        return OrchestratorService.get(db, user_id, plan_row.id)

    @staticmethod
    def execute(db: Session, user_id: int, plan_id: int) -> dict:
        from app.modules.outcome.service import OutcomeService
        from app.modules.profile.service import ProfileService
        from app.modules.reputation.service import ReputationService
        from app.modules.reward.service import RewardService
        from app.modules.runtime.service import RuntimeService
        from app.modules.service.service import ServiceRegistry

        plan_row = db.scalar(select(OrchestrationPlan).where(
            OrchestrationPlan.id == plan_id,
            OrchestrationPlan.user_id == user_id,
        ))
        if plan_row is None:
            raise AppError(NOT_FOUND, "Orchestration plan not found", 404)
        if plan_row.status in ("completed", "partial", "failed"):
            return OrchestratorService.get(db, user_id, plan_id)
        if plan_row.status == "running":
            raise AppError(CONFLICT, "This plan is already running", 409)
        steps = db.scalars(
            select(OrchestrationStep)
            .where(OrchestrationStep.plan_id == plan_id)
            .order_by(OrchestrationStep.step_order)
        ).all()
        if not steps:
            raise AppError(CONFLICT, "Plan has no service steps", 409)

        plan_row.status = "running"
        db.commit()
        previous_output = ""
        successful = 0
        failed = False
        for step in steps:
            if failed:
                step.status = "skipped"
                step.output = {"reason": "A previous step did not produce a safe result."}
                continue
            service = ServiceRegistry.get(db, step.service_id)
            version = ServiceRegistry.current_version(db, service)
            if version is None:
                step.status = "failed"
                step.output = {"reason": "Service has no active version."}
                failed = True
                continue

            session = RuntimeService.start_session(db, user_id, service.id, version.id, None)
            message = (
                f"Overall goal: {plan_row.goal_text}\n"
                f"Your part of the goal ({step.role}): provide a useful, concrete result.\n"
                + (f"Previous step result to build on:\n{previous_output}" if previous_output else "")
            )
            run = RuntimeService.execute(db, session, version, service.name, message, {}, {})
            step.session_id = session.id
            step.output = {
                "ok": bool(run.get("ok")),
                "content": (run.get("content") or "")[:1800],
                "deliverable": run.get("deliverable"),
                "failure": run.get("failure"),
            }
            if not run.get("ok"):
                step.status = "failed"
                step.score = 0.0
                failed = True
                # Record the failed run and trust delta, but do not award it or feed it forward.
                failed_outcome = OutcomeService.evaluate(db, session, version, run)
                ReputationService.apply_outcome_event(
                    db,
                    service.creator_id,
                    service.id,
                    failed_outcome.status,
                    session_id=session.id,
                    score=failed_outcome.score,
                )
                continue

            step.status = "done"
            previous_output = (run.get("content") or "")[:1200]
            outcome = OutcomeService.evaluate(db, session, version, run)
            step.score = outcome.score
            successful += 1
            ReputationService.apply_outcome_event(
                db,
                service.creator_id,
                service.id,
                outcome.status,
                session_id=session.id,
                score=outcome.score,
            )
            RewardService.process_outcome(db, user_id, session.id, outcome.status, outcome.score)
            creator = ProfileService.get_creator_by_id(db, service.creator_id)
            if creator:
                RewardService.process_outcome(db, creator.user_id, session.id, outcome.status, outcome.score)

        plan_row.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if successful == len(steps):
            plan_row.status = "completed"
        elif successful:
            plan_row.status = "partial"
        else:
            plan_row.status = "failed"
        plan_row.summary = f"{successful} of {len(steps)} service step(s) completed."
        from app.shared.audit import record

        record(db, user_id, "orchestration.plan.executed", plan_id, {
            "status": plan_row.status,
            "successful_steps": successful,
            "total_steps": len(steps),
        })
        db.commit()
        return OrchestratorService.get(db, user_id, plan_id)

    @staticmethod
    def get(db: Session, user_id: int, plan_id: int) -> dict:
        plan_row = db.scalar(select(OrchestrationPlan).where(
            OrchestrationPlan.id == plan_id,
            OrchestrationPlan.user_id == user_id,
        ))
        if plan_row is None:
            raise AppError(NOT_FOUND, "Orchestration plan not found", 404)
        steps = db.scalars(
            select(OrchestrationStep)
            .where(OrchestrationStep.plan_id == plan_id)
            .order_by(OrchestrationStep.step_order)
        ).all()
        result = plan_row.as_dict()
        result["steps"] = [step.as_dict() for step in steps]
        return result

    @staticmethod
    def list_for(db: Session, user_id: int) -> list[dict]:
        rows = db.scalars(
            select(OrchestrationPlan)
            .where(OrchestrationPlan.user_id == user_id)
            .order_by(OrchestrationPlan.id.desc())
        ).all()
        return [OrchestratorService.get(db, user_id, row.id) for row in rows]
