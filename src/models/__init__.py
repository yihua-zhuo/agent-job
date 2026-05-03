"""Models package for CRM system."""
from .customer import Customer, CustomerStatus
from .opportunity import Opportunity, Stage
from .pipeline import Pipeline
from .user import User, Role
from .activity import Activity, ActivityType
from .marketing import Campaign, CampaignEvent, CampaignStatus, CampaignType, TriggerType

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