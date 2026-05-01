"""Unit tests for Pipeline model."""
import pytest
from models.pipeline import Pipeline
from models.opportunity import Stage


class TestPipelineInit:
    """Tests for Pipeline __post_init__ method."""

    def test_post_init_sets_id_to_none_when_none(self):
        """Lines 21-22: id is None stays None."""
        p = Pipeline(name="Test", stages=[])
        assert p.id is None

    def test_post_init_clears_empty_stages_list(self):
        """Lines 23-24: empty stages list is cleared to empty list."""
        p = Pipeline(name="Test", stages=[])
        assert p.stages == []

    def test_post_init_sets_is_default_false_when_none(self):
        """Lines 25-26: is_default None becomes False."""
        p = Pipeline(name="Test", stages=[], is_default=None)
        assert p.is_default is False

    def test_post_init_does_not_override_explicit_values(self):
        """Non-None values are not overridden."""
        p = Pipeline(name="Test", stages=[Stage.QUALIFIED], id=5, is_default=True)
        assert p.id == 5
        assert p.is_default is True
        assert p.stages == [Stage.QUALIFIED]


class TestPipelineToDict:
    """Tests for Pipeline.to_dict() method."""

    def test_to_dict_includes_all_fields(self):
        """Line 30: to_dict returns all fields."""
        p = Pipeline(
            id=1,
            tenant_id=10,
            name="Sales Pipeline",
            stages=[Stage.LEAD, Stage.QUALIFIED],
            is_default=True
        )
        d = p.to_dict()
        assert d['id'] == 1
        assert d['tenant_id'] == 10
        assert d['name'] == "Sales Pipeline"
        assert d['stages'] == ['lead', 'qualified']
        assert d['is_default'] is True

    def test_to_dict_converts_stage_enum_to_value(self):
        """Line 34: Stage enum is converted to string value."""
        p = Pipeline(name="P", stages=[Stage.LEAD])
        assert p.to_dict()['stages'] == ['lead']


class TestPipelineFromDict:
    """Tests for Pipeline.from_dict() class method."""

    def test_from_dict_parses_string_stage(self):
        """Lines 46-47: string stage is converted to Stage enum."""
        data = {
            'name': 'Test Pipeline',
            'stages': ['lead', 'qualified']
        }
        pipeline = Pipeline.from_dict(data)
        assert pipeline.stages == [Stage.LEAD, Stage.QUALIFIED]

    def test_from_dict_keeps_stage_enum(self):
        """Lines 44-45: Stage enum is kept as-is."""
        data = {
            'name': 'Test Pipeline',
            'stages': [Stage.LEAD, Stage.NEGOTIATION]
        }
        pipeline = Pipeline.from_dict(data)
        assert pipeline.stages == [Stage.LEAD, Stage.NEGOTIATION]

    def test_from_dict_handles_empty_stages(self):
        """Lines 41-42: missing stages defaults to empty list."""
        data = {'name': 'No Stages'}
        pipeline = Pipeline.from_dict(data)
        assert pipeline.stages == []

    def test_from_dict_uses_default_values(self):
        """Lines 49-54: default values for optional fields."""
        data = {'name': 'Minimal'}
        pipeline = Pipeline.from_dict(data)
        assert pipeline.id is None
        assert pipeline.tenant_id == 0
        assert pipeline.is_default is False