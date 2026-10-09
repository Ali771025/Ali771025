"""Intent schemas — the structured output shape is normative (API_CONTRACT §4)."""
from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    primary_intent: str
    secondary_intents: list[str] = Field(default_factory=list)
    entities: dict = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)
    confidence: float
    ambiguous: bool = False


class IntentCatalogItem(BaseModel):
    slug: str
    name: str
    description: str
    capabilities: list[str]
