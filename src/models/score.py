"""Score schemas for lead scoring."""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field


class ScoreTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class SimilarLead(BaseModel):
    """A single similar-lead entry returned by AI enrichment."""

    id: int
    score: float
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render as a plain dict."""
        return {"id": self.id, "score": self.score, "name": self.name}


class ScoreRequest(BaseModel):
    """Input schema for lead scoring — passed to the scoring engine.

    Fields mirror the input accepted by SmartCategorizationService.score_lead():
    source, company_size, title, engaged_actions.
    """

    model_config = {"str_strip_whitespace": True}

    customer_id: Annotated[int, Field(gt=0)]
    tenant_id: Annotated[int, Field(gt=0)]
    source: Annotated[str, Field(min_length=1, max_length=50)]
    company_size: Annotated[int, Field(ge=0)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    engaged_actions: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Render as a plain dict."""
        return {
            "customer_id": self.customer_id,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "company_size": self.company_size,
            "title": self.title,
            "engaged_actions": self.engaged_actions,
        }


class ScoreResponse(BaseModel):
    """Output schema returned after scoring a lead."""

    score: int | None = None
    tier: str | None = None
    score_factors: dict | None = None
    top_factors: list | None = None
    recommendations: list | None = None
    similar_leads: list[SimilarLead] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render as a plain dict, omitting None values for consistency with router output."""
        data: dict[str, Any] = {
            "score": self.score,
            "tier": self.tier,
            "score_factors": self.score_factors,
            "top_factors": self.top_factors,
            "recommendations": self.recommendations,
        }
        if self.similar_leads is not None:
            data["similar_leads"] = [sl.to_dict() if hasattr(sl, "to_dict") else sl for sl in self.similar_leads]
        return data
