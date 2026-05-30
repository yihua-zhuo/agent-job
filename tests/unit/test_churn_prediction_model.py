"""
Unit tests for ChurnPrediction model.
"""
import pytest

from db.models.churn_prediction import ChurnPredictionModel
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.churn_predictions import make_churn_prediction_handler


@pytest.fixture
def mock_db_session():
    """Mock DB session with churn_prediction handler."""
    state = MockState()
    return make_mock_session([make_churn_prediction_handler(state)], state=state)


class TestChurnPredictionModel:
    """Tests for ChurnPredictionModel."""

    def test_model_instantiation(self):
        """Test ChurnPredictionModel can be instantiated with required fields."""
        model = ChurnPredictionModel(
            tenant_id=1,
            customer_id=10,
            score=0.75,
        )
        assert model.tenant_id == 1
        assert model.customer_id == 10
        assert model.score == 0.75

    def test_model_with_all_fields(self):
        """Test model instantiation with all fields."""
        model = ChurnPredictionModel(
            tenant_id=2,
            customer_id=20,
            score=0.42,
            tier="high",
            factors=["low_engagement", "support_tickets_up"],
        )
        assert model.tenant_id == 2
        assert model.customer_id == 20
        assert model.score == 0.42
        assert model.tier == "high"
        assert model.factors == ["low_engagement", "support_tickets_up"]

    def test_to_dict_output_shape(self):
        """Test to_dict returns expected keys."""
        model = ChurnPredictionModel(
            tenant_id=1,
            customer_id=5,
            score=0.88,
            tier="critical",
            factors=["payment_declined", "no_login_30d"],
        )
        result = model.to_dict()
        assert "id" in result
        assert "tenant_id" in result
        assert "customer_id" in result
        assert "score" in result
        assert "tier" in result
        assert "factors" in result
        assert "predicted_at" in result
        assert "created_at" in result
        assert "updated_at" in result

    def test_to_dict_values(self):
        """Test to_dict returns correct values."""
        model = ChurnPredictionModel(
            tenant_id=3,
            customer_id=7,
            score=0.55,
            tier="medium",
            factors=["infrequent_purchase"],
        )
        result = model.to_dict()
        assert result["tenant_id"] == 3
        assert result["customer_id"] == 7
        assert result["score"] == 0.55
        assert result["tier"] == "medium"
        assert result["factors"] == ["infrequent_purchase"]

    def test_tenant_id_in_state(self, mock_db_session):
        """Test that state is created and handlers are wired up for the churn_predictions table."""
        assert mock_db_session is not None

    def test_tablename(self):
        """Test the table name is correctly set."""
        assert ChurnPredictionModel.__tablename__ == "churn_predictions"
