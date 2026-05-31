"""Unit tests for CustomerEnrichment ORM model."""

from db.base import Base

# Prefer the already-registered class when db.models.__init__.py loaded it
# during test collection.  Fall back to a direct filesystem load when this
# test file is collected in isolation (no other module has touched
# customer_enrichment yet).
if "customer_enrichments" in Base.metadata.tables:
    from db.models.customer_enrichment import CustomerEnrichmentModel
else:
    import importlib.util
    import sys
    from pathlib import Path

    _model_path = Path(__file__).resolve().parents[2] / "src" / "db" / "models" / "customer_enrichment.py"
    _spec = importlib.util.spec_from_file_location("customer_enrichment_model", _model_path)
    _module = importlib.util.module_from_spec(_spec)
    _src_root = Path(__file__).resolve().parents[2] / "src"
    if str(_src_root) not in sys.path:
        sys.path.insert(0, str(_src_root))
    _spec.loader.exec_module(_module)
    CustomerEnrichmentModel = _module.CustomerEnrichmentModel

from datetime import UTC, datetime


class TestCustomerEnrichmentModel:
    """Tests for CustomerEnrichmentModel."""

    def test_create_enrichment_defaults(self):
        """Test enrichment creation with required fields and default values."""
        enrichment = CustomerEnrichmentModel(
            customer_id=1,
            provider="clearbit",
        )

        assert enrichment.customer_id == 1
        assert enrichment.provider == "clearbit"
        # Python-level default is not applied on construction; to_dict() handles it
        assert enrichment.raw_data_json is None
        assert enrichment.enriched_at is None
        assert enrichment.next_refresh_at is None

    def test_to_dict(self):
        """Test enrichment to_dict conversion with all fields."""
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        enrichment = CustomerEnrichmentModel(
            id=5,
            customer_id=10,
            provider="fullcontact",
            raw_data_json={"name": "Acme Corp", "employees": 500},
            enriched_at=now,
            next_refresh_at=now,
        )

        result = enrichment.to_dict()

        assert result["id"] == 5
        assert result["customer_id"] == 10
        assert result["provider"] == "fullcontact"
        assert result["raw_data_json"] == {"name": "Acme Corp", "employees": 500}
        assert result["enriched_at"] == now.isoformat()
        assert result["next_refresh_at"] == now.isoformat()
        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_to_dict_with_none_datetimes(self):
        """Test to_dict handles None datetimes gracefully."""
        enrichment = CustomerEnrichmentModel(
            customer_id=1,
            provider="clearbit",
            raw_data_json={},
        )

        result = enrichment.to_dict()

        assert result["enriched_at"] is None
        assert result["next_refresh_at"] is None
        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_raw_data_json_default(self):
        """Test raw_data_json defaults to None on Python object; to_dict() returns {}."""
        enrichment = CustomerEnrichmentModel(
            customer_id=1,
            provider="clearbit",
        )
        assert enrichment.raw_data_json is None
        assert enrichment.to_dict()["raw_data_json"] == {}

    def test_raw_data_json_with_complex_data(self):
        """Test raw_data_json stores complex nested data."""
        complex_data = {
            "company": {
                "name": "Acme",
                "metrics": {"revenue": 1_000_000, "employees": 50},
            },
            "tags": ["enterprise", "saas"],
        }
        enrichment = CustomerEnrichmentModel(
            customer_id=1,
            provider="clearbit",
            raw_data_json=complex_data,
        )
        assert enrichment.raw_data_json == complex_data
        assert enrichment.raw_data_json["company"]["metrics"]["employees"] == 50

    def test_customer_id_required(self):
        """Test that customer_id is required (not None) when creating an enrichment."""
        enrichment = CustomerEnrichmentModel(customer_id=42, provider="clearbit")
        assert enrichment.customer_id == 42

    def test_provider_required(self):
        """Test that provider is required when creating an enrichment."""
        enrichment = CustomerEnrichmentModel(customer_id=1, provider="clearbit")
        assert enrichment.provider == "clearbit"
