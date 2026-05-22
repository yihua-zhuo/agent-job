"""Pydantic request/response schemas for AI-generated email and SMS drafts."""

from enum import StrEnum

from pydantic import BaseModel, model_validator

from pkg.errors.app_exceptions import ValidationException


class TemplateType(StrEnum):
    EMAIL = "email"
    SMS = "sms"


class DraftType(StrEnum):
    EMAIL = "email"
    SMS = "sms"


class ToneType(StrEnum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    URGENT = "urgent"


class DraftContext(BaseModel):
    customer_id: int
    opportunity_id: int | None = None
    template_type: TemplateType


class DraftRequest(BaseModel):
    type: DraftType
    subject: str | None = None
    tone: ToneType
    context: DraftContext

    @model_validator(mode="after")
    def subject_required_for_email(self) -> "DraftRequest":
        if self.type == DraftType.EMAIL and self.subject is None:
            raise ValidationException("subject is required when type is EMAIL")
        return self


class SuggestedAction(BaseModel):
    label: str
    action_type: str
    payload: dict


class DraftResponse(BaseModel):
    body: str
    suggested_actions: list[SuggestedAction]

    def to_dict(self) -> dict:
        return self.model_dump()
