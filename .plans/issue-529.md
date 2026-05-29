Now I have a complete picture of the codebase. Let me compile the plan.

The issue says fields `status`, `type`, `sent_at`, `open_rate`, `click_rate` may be missing. What the code actually shows:

- **`status`** and **`type`** — both exist in `CampaignModel` and `to_dict()`. However, the create endpoint at `src/api/routers/marketing.py:92–107` does NOT forward `body.status` or `body.type` to the service, so they are silently ignored on creation.
- **`sent_at`** — entirely absent from the model, migration, and service.
- **`open_rate`** and **`click_rate`** — computed (not stored) in `MarketingService.get_campaign_stats()` only; never persisted to the model and never in `to_dict()`.

The router's schema (`CampaignCreate`) already accepts `status` and `type`, so the fix is to wire them through. `sent_at` needs model + migration + service plumbing. `open_rate`/`click_rate` are intentionally derived in the stats method and don't belong on the model.

---

# Implementation Plan — Issue #529

## Goal
Add the missing `sent_at` datetime column to `CampaignModel`, wire `status` and `type` from the `CampaignCreate` request body into the service's `create_campaign()` call, and add a corresponding Alembic migration — closing the gaps between the router schema, service layer, and ORM model.

## Affected Files
- `src/db/models/marketing.py` — add `sent_at` column and update `to_dict()`
- `src/services/marketing_service.py` — set `sent_at` in `create_campaign()` and add `set_sent_at()` method
- `src/api/routers/marketing.py` — pass `status` and `type` from `CampaignCreate` body into the service call
- `alembic/versions/<new_revision>.py` — add `sent_at` column to the `campaigns` table
- `alembic/env.py` — no change needed (`import db.models` already imports `db.models.marketing`)
- `tests/unit/test_marketing_router.py` — add `sent_at` to `CAMPAIGN_ROW` fixture so mocked `to_dict()` output matches the updated model
- `tests/integration/test_marketing_integration.py` — add a test that launches a campaign and verifies `sent_at` is set; add a test that passes non-default `status`/`type` on create and verifies they are persisted

## Implementation Steps

1. **Add `sent_at` to `CampaignModel`** (`src/db/models/marketing.py`):
   - Add `sent_at: Mapped[datetime | None]` as a nullable `DateTime(timezone=True)` column (no server default — will be null until campaign is sent)
   - Add `"sent_at": self.sent_at.isoformat() if self.sent_at else None` to `to_dict()`

2. **Update `MarketingService.create_campaign()`** (`src/services/marketing_service.py`):
   - Accept optional `sent_at` kwarg and assign it to the model
   - Add a new `set_sent_at()` method that calls `update_campaign()` with the current UTC timestamp

3. **Fix `CampaignCreate` forwarding in the router** (`src/api/routers/marketing.py:98–106`):
   - Pass `status=body.status` and `campaign_type=body.type` into `svc.create_campaign()` so non-default values are not silently dropped

4. **Generate an Alembic migration** for the new `sent_at` column:
   - Using the workflow from `CLAUDE.md`: spin up a disposable `alembic_dev` DB, run `alembic upgrade head`, then `alembic revision --autogenerate -m "add_sent_at_to_campaigns"`, review the generated file, and verify up/down cycle
   - The migration must `op.add_column('sent_at', ...)` in `upgrade()` and `op.drop_column('sent_at')` in `downgrade()`

5. **Update `CAMPAIGN_ROW` in unit tests** (`tests/unit/test_marketing_router.py`):
   - Add `"sent_at": None` (or a timestamp string) so the `mock_campaign.to_dict()` return value matches the new field in `CampaignModel.to_dict()`

6. **Run all tests** to confirm nothing is broken:
   - `ruff check src/` and `ruff format --check src/`
   - `pytest tests/unit/ -v`
   - `pytest tests/integration/ -v` (requires `DATABASE_URL`)

## Test Plan
- **Unit tests in `tests/unit/test_marketing_integration.py`** (new file or additions to existing): Add test cases in `TestCreateCampaignEndpoint` verifying that `status` and `type` from the request body are forwarded to the service. Mock `svc.create_campaign` and assert it is called with the correct `campaign_type` kwarg.
- **Integration tests in `tests/integration/test_marketing_integration.py`**: Add `test_sent_at_set_on_launch()` that calls `svc.launch_campaign()` and asserts the returned campaign has a non-null `sent_at`; add `test_create_with_non_default_status_and_type()` that passes `status="scheduled"` and `type="sms"` on create and asserts the persisted record reflects those values.

## Acceptance Criteria
- `CampaignModel` has a `sent_at` column visible to Alembic (`import db.models` in `alembic/env.py` already covers this)
- `CampaignModel.to_dict()` includes `"sent_at"`
- `svc.create_campaign()` accepts and stores `sent_at` via kwargs; `svc.launch_campaign()` sets `sent_at` to UTC now
- `POST /api/v1/marketing/campaigns` forwards `body.status` and `body.type` to the service
- All existing unit tests in `tests/unit/test_marketing_router.py` pass
- All existing integration tests in `tests/integration/test_marketing_integration.py` pass
- The generated Alembic migration applies and rolls back cleanly
