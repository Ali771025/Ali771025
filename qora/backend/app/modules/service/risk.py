"""Risk classification and eligibility gates [PRD: risk-based verification].

A creator-supplied label can raise risk, but cannot lower the platform's classification.
"""
import re

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "RESTRICTED": 3}

_HIGH_RISK = re.compile(
    r"\b(medical|clinical|diagnos(?:e|is)|prescription|medication|therapy|"
    r"finance|financial|investment|securities|tax advice|legal advice|attorney|lawsuit|debt relief)\b"
)
_MEDIUM_RISK = re.compile(
    r"\b(career|job search|startup|business|education|tutoring|personal finance)\b"
)
_RESTRICTED = re.compile(
    r"\b(make a bomb|build malware|steal credit cards|child exploitation|"
    r"harm myself|harm someone|evade law enforcement)\b"
)


class RiskService:
    @staticmethod
    def classify(text: str, creator_label: str | None = None) -> str:
        """Return the stricter of the inferred and creator-declared risk levels."""
        low = (text or "").lower()
        inferred = "LOW"
        if _RESTRICTED.search(low):
            inferred = "RESTRICTED"
        elif _HIGH_RISK.search(low):
            inferred = "HIGH"
        elif _MEDIUM_RISK.search(low):
            inferred = "MEDIUM"
        declared = creator_label if creator_label in RISK_ORDER else "LOW"
        return max((inferred, declared), key=RISK_ORDER.get)

    @staticmethod
    def publication_blockers(service, creator, version=None) -> list[str]:
        level = getattr(service, "risk_level", "LOW") or "LOW"
        blockers: list[str] = []
        if level == "RESTRICTED":
            return ["This service is not eligible for publication."]
        boundaries = getattr(version, "boundaries", "") if version else ""
        if level in ("MEDIUM", "HIGH") and len(boundaries or "") < 12:
            blockers.append("Add clear safety boundaries before publication.")
        if level == "HIGH":
            if not creator or creator.verification_status != "verified":
                blockers.append("Creator verification is required for high-risk services.")
            if getattr(service, "verification_status", "none") != "verified":
                blockers.append("This service needs a platform review before publication.")
        return blockers

    @staticmethod
    def runtime_gate(service, creator, version) -> tuple[bool, str | None]:
        blockers = RiskService.publication_blockers(service, creator, version)
        if blockers:
            return False, " ".join(blockers)
        return True, None

    @staticmethod
    def eligible_for_discovery(service, creator, version=None) -> bool:
        return not RiskService.publication_blockers(service, creator, version)
