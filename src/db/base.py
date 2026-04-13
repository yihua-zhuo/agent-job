"""SQLAlchemy declarative Base for all ORM models."""
from sqlalchemy.orm import DeclarativeBase

from src.db.models import (
    ActivityModel,
    CampaignEventModel,
    CampaignModel,
    CustomerModel,
    NotificationModel,
    OpportunityModel,
    PipelineModel,
    PipelineStageModel,
    ReminderModel,
    TaskModel,
    TenantModel,
    TicketModel,
    TicketReplyModel,
    UserModel,
)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass