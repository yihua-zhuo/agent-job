from pydantic import BaseModel, Field


class ChannelDelivery(BaseModel):
    """Represents a single routing decision — which channel to deliver a notification on."""

    channel: str = Field(description="Delivery channel: in_app | email | batch")
    target: str = Field(
        description="Recipient address: user_id for in_app, email addr for email, 'daily_digest' for batch"
    )
    priority: str = Field(description="Original notification priority: urgent | normal | low")
    status: str = Field(default="pending", description="Routing status: pending | routed")
    tenant_id: int = Field(description="Tenant for multi-tenant isolation")

    model_config = {"from_attributes": True}
