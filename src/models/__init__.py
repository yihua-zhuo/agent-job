"""Models package for CRM system."""
from .activity import Activity, ActivityType
from .customer import Customer, CustomerStatus
from .marketing import Campaign, CampaignEvent, CampaignStatus, CampaignType, TriggerType
from .opportunity import Opportunity, Stage
from .pipeline import Pipeline
from .user import Role, User

__all__ = [
    'Customer',
    'CustomerStatus',
    'Opportunity',
    'Stage',
    'Pipeline',
    'User',
    'Role',
    'Activity',
    'ActivityType',
    'Campaign',
    'CampaignEvent',
    'CampaignStatus',
    'CampaignType',
    'TriggerType',
]
