"""Opportunity model for CRM system."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class Stage(Enum):
    """Sales pipeline stage enumeration."""
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


@dataclass
class Opportunity:
    """Opportunity entity representing a sales opportunity."""
    customer_id: int
    name: str
    stage: Stage
    amount: Decimal
    probability: int
    expected_close_date: datetime
    owner_id: int
    pipeline_id: int
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Initialize default values after dataclass initialization."""
        if self.id is None:
            self.id = None
        if self.stage is None:
            self.stage = Stage.LEAD
        if self.probability is None:
            self.probability = 0
        # Clamp probability to 0-100 range
        if self.probability < 0:
            self.probability = 0
        elif self.probability > 100:
            self.probability = 100
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert opportunity to dictionary representation."""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'name': self.name,
            'stage': self.stage.value if isinstance(self.stage, Stage) else self.stage,
            'amount': str(self.amount) if isinstance(self.amount, Decimal) else self.amount,
            'probability': self.probability,
            'expected_close_date': self.expected_close_date.isoformat() if isinstance(self.expected_close_date, datetime) else self.expected_close_date,
            'owner_id': self.owner_id,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Opportunity':
        """Create opportunity instance from dictionary."""
        stage_value = data.get('stage')
        if isinstance(stage_value, str):
            stage = Stage(stage_value)
        else:
            stage = stage_value or Stage.LEAD

        amount_value = data.get('amount')
        if isinstance(amount_value, str):
            amount = Decimal(amount_value)
        elif isinstance(amount_value, (int, float)):
            amount = Decimal(str(amount_value))
        else:
            amount = Decimal('0')

        expected_close_date = data.get('expected_close_date')
        if isinstance(expected_close_date, str):
            expected_close_date = datetime.fromisoformat(expected_close_date)
        elif expected_close_date is None:
            expected_close_date = datetime.utcnow()

        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            id=data.get('id'),
            customer_id=data['customer_id'],
            name=data['name'],
            stage=stage,
            amount=amount,
            probability=data.get('probability', 0),
            expected_close_date=expected_close_date,
            owner_id=data['owner_id'],
            pipeline_id=data.get('pipeline_id', 0),
            created_at=created_at,
            updated_at=updated_at,
        )
