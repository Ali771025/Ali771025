"""Qualification Engine [PRD] — six criteria + duplicate control.

Duplicate Detection [TECH]: intent/capability/outcome embeddings → similarity →
a DIFFERENTIATION QUESTION, never an automatic rejection (ARCHITECTURE §4.23).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.qualification.models import DuplicateCheck, QualificationRun
from app.modules.qualification.simulation import SimulationEngine
from app.shared.embeddings import cosine, embed_text

SIM_THRESHOLD = 0.7


def _service_embed_text(spec: dict) -> str:
    parts = [
        spec.get("name", ""),
        spec.get("purpose", ""),
        " ".join(spec.get("capabilities", []) or []),
        (spec.get("outcome_definition") or {}).get("text", ""),
        spec.get("audience", ""),
    ]
    return " ".join(p for p in parts if p)


class QualificationEngine:
    @staticmethod
    def run(db: Session, service_id: int, service_version_id: int | None, interview_id: int | None, spec: dict) -> QualificationRun:
        qrun = QualificationRun(
            service_id=service_id,
            service_version_id=service_version_id,
            interview_id=interview_id,
        )
        db.add(qrun)
        db.flush()

        checks: list[dict] = []
        scores: dict[str, float] = {}

        def check(criterion: str, passed: bool, score: float, detail: str):
            checks.append({"criterion": criterion, "passed": passed, "detail": detail})
            scores[criterion] = score

        # 1. Specification Check
        required = ["purpose", "audience", "method", "behavior", "boundaries", "outcome_definition"]
        missing = [f for f in required if not spec.get(f)]
        check("specification", not missing, 1.0 if not missing else 0.4,
              "complete" if not missing else f"missing fields: {', '.join(missing)}")

        # 2. Outcome Check
        od = spec.get("outcome_definition") or {}
        ok = bool(od.get("text")) and bool(od.get("signals"))
        check("outcome", ok, 1.0 if ok else 0.3,
              "outcome defined with measurable signals" if ok else "outcome_definition needs text + signals")

        # 3. Safety Evaluation
        risk = spec.get("risk_classification", "LOW")
        boundaries = spec.get("boundaries") or ""
        safe = len(boundaries) > 20 and risk in ("LOW", "MEDIUM", "HIGH", "RESTRICTED")
        if risk == "RESTRICTED":
            check("safety", False, 0.2, "restricted risk — not eligible for automatic qualification")
        else:
            check("safety", safe, 0.9 if safe else 0.35,
                  f"risk={risk}, boundaries {'present' if safe else 'too weak'}")

        # 4. Boundary Evaluation
        refusal = any(t in boundaries.lower() for t in ("not", "no ", "refuse", "never", "avoid", "outside", "beyond", "cannot", "won't"))
        check("boundaries", refusal, 0.9 if refusal else 0.4,
              "explicit refusal language present" if refusal else "add explicit negative boundaries")

        # 5. Reliability Simulation
        sim = SimulationEngine.latest_for_service(db, service_id)
        if not sim or sim.status != "done":
            sim = SimulationEngine.run(db, service_id, interview_id, spec)
        avg = float((sim.summary or {}).get("avg_score", 0))
        check("reliability", avg >= SIM_THRESHOLD, avg, f"simulation avg score {avg} ({(sim.summary or {}).get('cases', 0)} cases)")

        # 6. Duplicate Detection (question, not rejection)
        dup_ok, dup_detail = QualificationEngine._duplicates(db, qrun.id, service_id, spec)
        check("differentiation", dup_ok, 1.0 if dup_ok else 0.6, dup_detail)

        # 7. Knowledge Check
        kc = spec.get("knowledge_requirements")
        has_kn = bool(spec.get("knowledge_version_id")) or kc in (None, "", "none", "not needed", "n/a")
        check("knowledge", has_kn, 1.0 if has_kn else 0.5,
              "knowledge attached or explicitly not needed" if has_kn else "attach training material or declare none is needed")

        # 8. Trust Requirement Check (creator profile completeness)
        check("trust", bool(spec.get("name") and spec.get("purpose")), 0.85, "creator identity on file")

        passed_all = all(c["passed"] for c in checks if c["criterion"] != "differentiation")
        hard_fail = any(c["criterion"] == "safety" and not c["passed"] for c in checks)

        if hard_fail:
            qrun.result = "RESTRICTED"
        elif passed_all and avg >= SIM_THRESHOLD:
            qrun.result = "READY_TO_PUBLISH"
        else:
            qrun.result = "NEEDS_IMPROVEMENT"

        qrun.scores = scores
        qrun.checks = checks
        qrun.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(qrun)
        return qrun

    @staticmethod
    def _duplicates(db: Session, qrun_id: int, service_id: int, spec: dict) -> tuple[bool, str]:
        # Boundary rule: query other services through the service module interface only.
        from app.modules.service.service import ServiceRegistry

        target_vec = embed_text(_service_embed_text(spec))
        rows = ServiceRegistry.discover(db, None, limit=50)
        found = []
        for row in rows:
            s = row["service"]
            if s.id == service_id:
                continue
            other = embed_text(_service_embed_text({
                "name": s.name,
                "purpose": s.purpose,
                "outcome_definition": {"text": s.summary},
                "audience": s.audience,
            }))
            sim = cosine(target_vec, other)
            if sim >= 0.55:
                found.append((sim, s.id, s.name))
                db.add(DuplicateCheck(
                    qualification_run_id=qrun_id,
                    similar_service_id=s.id,
                    similar_service_name=s.name,
                    similarity=sim,
                    resolution="needs_differentiation" if sim >= 0.7 else "unique",
                    question=f"Your service is {round(sim * 100)}% similar to “{s.name}” — what makes your method different?",
                ))
        if not found:
            return True, "no similar services found"
        top = max(found)
        return False, f"similar to “{top[2]}” ({round(top[0] * 100)}%) — answer the differentiation question (this is NOT a rejection)"

    @staticmethod
    def get_run(db: Session, run_id: int) -> dict | None:
        qrun = db.get(QualificationRun, run_id)
        if not qrun:
            return None
        dups = db.scalars(select(DuplicateCheck).where(DuplicateCheck.qualification_run_id == run_id)).all()
        return {
            "id": qrun.id,
            "service_id": qrun.service_id,
            "result": qrun.result,
            "scores": qrun.scores,
            "checks": qrun.checks,
            "duplicates": [
                {
                    "similar_service_id": d.similar_service_id,
                    "similar_service_name": d.similar_service_name,
                    "similarity": d.similarity,
                    "resolution": d.resolution,
                    "question": d.question,
                }
                for d in dups
            ],
            "started_at": qrun.started_at,
            "finished_at": qrun.finished_at,
        }
