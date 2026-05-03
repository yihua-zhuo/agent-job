"""Pipeline model for CRM system."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

# Import Stage from opportunity module to avoid duplication
from .opportunity import Stage


@dataclass
class Pipeline:
    """Pipeline entity representing a sales pipeline with stages."""
    name: str
    stages: List[Stage]
    id: Optional[int] = None
    is_default: bool = False

    def __post_init__(self) -> None:
        """Initialize default values after dataclass initialization."""
        if self.id is None:
            self.id = None
        if not self.stages:
            self.stages = []
        if self.is_default is None:
            self.is_default = False

    def to_dict(self) -> dict:
        """Convert pipeline to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'stages': [s.value if isinstance(s, Stage) else s for s in self.stages],
            'is_default': self.is_default,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Pipeline':
        """Create pipeline instance from dictionary."""
        stages_data = data.get('stages', [])
        stages = []
        for s in stages_data:
            if isinstance(s, Stage):
                stages.append(s)
            elif isinstance(s, str):
                stages.append(Stage(s))

        return cls(
            id=data.get('id'),
            name=data['name'],
            stages=stages,
            is_default=data.get('is_default', False),
        )