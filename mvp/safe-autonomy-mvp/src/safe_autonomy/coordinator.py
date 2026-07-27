from __future__ import annotations

from dataclasses import dataclass

from .advisory import (
    AdvisoryIntent,
    AdvisoryProposal,
    AdvisoryRepository,
    DeterministicDecisionEngine,
    EvidenceGate,
    OllamaAdvisoryClient,
    OperationalDecision,
    ProposalGateResult,
    deterministic_proposal,
)
from .hybrid_rag import HybridRagEngine, RagResult
from .sensor_contracts import TelemetryFrame


@dataclass(frozen=True, slots=True)
class CoordinationResult:
    deterministic_decision: OperationalDecision
    rag_result: RagResult
    proposal: AdvisoryProposal
    gate: ProposalGateResult


class DecisionCoordinator:
    """Joins deterministic state, evidence retrieval and optional LLM advisory."""

    def __init__(
        self,
        decision_engine: DeterministicDecisionEngine,
        rag_engine: HybridRagEngine,
        evidence_gate: EvidenceGate,
        repository: AdvisoryRepository,
        llm: OllamaAdvisoryClient | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.rag_engine = rag_engine
        self.evidence_gate = evidence_gate
        self.repository = repository
        self.llm = llm

    def evaluate(self, request_id: str, frame: TelemetryFrame, now_ms: int) -> CoordinationResult:
        deterministic = self.decision_engine.decide(frame)
        observed_classes = ", ".join(sorted({obj.class_name for obj in frame.perception_objects}))
        perception_context = f"YOLO perception classes: {observed_classes}" if observed_classes else "No perception objects"
        retrieval_hints = {
            AdvisoryIntent.HOLD: "داده ناهمگام GPS IMU توقف ایمن",
            AdvisoryIntent.RETURN: "انرژی باتری ذخیره بازگشت",
            AdvisoryIntent.LAND: "انرژی باتری بحرانی فرود",
            AdvisoryIntent.REQUEST_REROUTE: "ادراک YOLO عمق tracking TTC تغییر مسیر",
            AdvisoryIntent.REQUEST_SENSOR_UPDATE: "ادراک YOLO عمق tracking TTC داده ناقص",
            AdvisoryIntent.ABORT_MISSION: "توقف ماموریت خطر بحرانی",
            AdvisoryIntent.CONTINUE: "رویه ایمنی ادامه",
            AdvisoryIntent.ABSTAIN: "اطلاعات ناکافی",
        }[deterministic.intent]
        query = (
            f"طبق رویه ایمن برای وضعیت {deterministic.intent.value} چه اقدام سطح بالایی مجاز است؟ "
            f"علت: {deterministic.reason}. کلیدواژه: {retrieval_hints}. "
            + perception_context
        )
        rag = self.rag_engine.query(query)
        if self.llm is None:
            proposal = deterministic_proposal(request_id, deterministic, frame, rag, now_ms)
        else:
            proposal = self.llm.propose(request_id, frame, rag, now_ms)
        gate = self.evidence_gate.validate(proposal, frame, rag, now_ms)
        self.repository.save(proposal, gate, frame.telemetry_frame_id, rag.query_id)
        return CoordinationResult(deterministic, rag, proposal, gate)
