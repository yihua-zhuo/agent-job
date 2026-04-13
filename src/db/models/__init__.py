"""Re-export all ORM models for convenience."""
from db.models.activity import ActivityModel
from db.models.analytics import DashboardModel, ReportModel
from db.models.customer import CustomerModel
from db.models.marketing import CampaignEventModel, CampaignModel
from db.models.notification import NotificationModel
from db.models.opportunity import OpportunityModel
from db.models.pipeline import PipelineModel
from db.models.pipeline_stage import PipelineStageModel
from db.models.reminder import ReminderModel
from db.models.task import TaskModel
from db.models.tenant import TenantModel
from db.models.ticket import TicketModel
from db.models.ticket_reply import TicketReplyModel
from db.models.user import UserModel

__all__ = [
    "ActivityModel",
    "CampaignEventModel",
    "CampaignModel",
    "CustomerModel",
    "DashboardModel",
    "NotificationModel",
    "OpportunityModel",
    "PipelineModel",
    "PipelineStageModel",
    "ReminderModel",
    "ReportModel",
    "TaskModel",
    "TenantModel",
    "TicketModel",
    "TicketReplyModel",
    "UserModel",
]