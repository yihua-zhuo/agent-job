"""Campaign SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState


def make_campaign_handler(state: MockState):
    """Handle campaign-related SQL."""

    def handler(sql_text, params):
        if "insert into campaigns" in sql_text:
            cid = getattr(state, "campaigns_next_id", 1)
            if not hasattr(state, "campaigns_next_id"):
                state.campaigns_next_id = 1
            state.campaigns_next_id += 1
            record = {
                "id": cid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Campaign"),
                "type": params.get("type", "email"),
                "status": params.get("status", "draft"),
                "subject": params.get("subject"),
                "content": params.get("content"),
                "target_audience": params.get("target_audience"),
                "trigger_type": params.get("trigger_type"),
                "trigger_days": params.get("trigger_days"),
                "created_by": params.get("created_by", 0),
                "sent_count": params.get("sent_count", 0),
                "open_count": params.get("open_count", 0),
                "click_count": params.get("click_count", 0),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            if not hasattr(state, "campaigns"):
                state.campaigns = {}
            state.campaigns[cid] = record
            return MockResult([MockRow(record.copy())])

        if "insert into campaign_events" in sql_text:
            eid = getattr(state, "campaign_events_next_id", 1)
            if not hasattr(state, "campaign_events_next_id"):
                state.campaign_events_next_id = 1
            state.campaign_events_next_id += 1
            record = {
                "id": eid,
                "tenant_id": params.get("tenant_id", 0),
                "campaign_id": params.get("campaign_id", 0),
                "customer_id": params.get("customer_id", 0),
                "event_type": params.get("event_type", "sent"),
                "created_at": params.get("created_at"),
            }
            if not hasattr(state, "campaign_events"):
                state.campaign_events = {}
            state.campaign_events[eid] = record
            return MockResult([MockRow(record.copy())])

        if "insert into campaign_triggers" in sql_text:
            tid = getattr(state, "trigger_next_id", 1)
            if not hasattr(state, "trigger_next_id"):
                state.trigger_next_id = 1
            state.trigger_next_id += 1
            record = {
                "id": tid,
                "tenant_id": params.get("tenant_id", 0),
                "campaign_id": params.get("campaign_id"),
                "name": params.get("name", "Trigger"),
                "type": params.get("type", "custom"),
                "conditions": params.get("conditions", {}),
                "is_active": params.get("is_active", True),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            if not hasattr(state, "triggers"):
                state.triggers = {}
            state.triggers[tid] = record
            return MockResult([MockRow(record.copy())])

        if "from campaigns where id" in sql_text:
            cid = params.get("id")
            tid = params.get("tenant_id")
            if (
                hasattr(state, "campaigns")
                and cid in state.campaigns
                and state.campaigns[cid].get("tenant_id") == tid
            ):
                return MockResult([MockRow(state.campaigns[cid].copy())])
            return MockResult([])

        if "from campaigns" in sql_text:
            tid = params.get("tenant_id")
            rows = []
            if hasattr(state, "campaigns"):
                rows = [
                    MockRow(r.copy())
                    for r in state.campaigns.values()
                    if r.get("tenant_id") == tid
                ]
            return MockResult(rows)

        if "from campaign_events" in sql_text:
            tid = params.get("tenant_id")
            rows = []
            if hasattr(state, "campaign_events"):
                rows = [
                    MockRow(r.copy())
                    for r in state.campaign_events.values()
                    if r.get("tenant_id") == tid
                ]
            return MockResult(rows)

        if "from campaign_triggers" in sql_text:
            tid = params.get("tenant_id")
            rows = []
            if hasattr(state, "triggers"):
                rows = [
                    MockRow(r.copy())
                    for r in state.triggers.values()
                    if r.get("tenant_id") == tid
                ]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_campaign_handler(state)]


__all__ = ["get_handlers", "make_campaign_handler"]
