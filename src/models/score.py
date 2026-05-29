"""Score schemas for lead scoring."""

from typing import Annotated, Any

from pydantic import BaseModel, Field


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

    def to_dict(self) -> dict[str, Any]:
        """Render as a plain dict."""
        return {
            "score": self.score,
            "tier": self.tier,
            "score_factors": self.score_factors,
            "top_factors": self.top_factors,
            "recommendations": self.recommendations,
        }
