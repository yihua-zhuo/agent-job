"""Pydantic schemas for lead routing rules and condition evaluation."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"


SUPPORTED_FIELDS = {"region", "industry", "employee_count", "source", "created_date", "company"}


class RuleCondition(BaseModel):
    """A single condition within a routing rule."""

    field: str = Field(..., description="Customer field to match on")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")

    def model_post_init(self, _):
        if self.field not in SUPPORTED_FIELDS:
            raise ValueError(f"Unsupported field: {self.field}. Supported: {sorted(SUPPORTED_FIELDS)}")


class RecycleHistoryEntry(BaseModel):
    """A single entry in the recycle history log."""

    recycled_at: datetime
    previous_owner_id: int
    reason: str | None = None


class RoutingRuleCreate(BaseModel):
    """Request body for creating a routing rule."""

    name: str = Field(..., min_length=1, max_length=255)
    conditions_json: list[RuleCondition] = Field(default_factory=list)
    assignee_type: str = Field(default="round_robin", pattern="^(user|team|round_robin)$")
    assignee_id: int | None = Field(None, ge=1)
    priority: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class RoutingRuleUpdate(BaseModel):
    """Request body for updating a routing rule."""

    name: str | None = Field(None, min_length=1, max_length=255)
    conditions_json: list[RuleCondition] | None = None
    assignee_type: str | None = Field(None, pattern="^(user|team|round_robin)$")
    assignee_id: int | None = Field(None, ge=1)
    priority: int | None = Field(None, ge=0)
    is_active: bool | None = None


class RoutingRuleResponse(BaseModel):
    """Response schema for a routing rule."""

    id: int
    tenant_id: int
    name: str
    conditions_json: list[dict]
    assignee_type: str
    assignee_id: int | None
    priority: int
    is_active: bool
    created_at: str | None
    updated_at: str | None


class RoutingRulePriorityUpdate(BaseModel):
    """Request body for bulk priority reordering."""

    rule_ids: list[int] = Field(..., min_length=1)


class LeadAssignPreview(BaseModel):
    """Preview of which rule and assignee would handle a lead."""

    matched_rule_id: int | None
    matched_rule_name: str | None
    assignee_id: int | None
    assignee_type: str
    sla_status: str  # "green" | "yellow" | "red"


class RuleTestRequest(BaseModel):
    """Request body for testing a rule without persisting changes."""

    conditions: list[RuleCondition] = Field(..., min_length=1)
    customer_data: dict[str, Any] = Field(..., description="Simulated customer record")


class LeadRecycleRequest(BaseModel):
    """Request body for manually triggering lead recycle."""

    customer_ids: list[int] = Field(..., min_length=1)
