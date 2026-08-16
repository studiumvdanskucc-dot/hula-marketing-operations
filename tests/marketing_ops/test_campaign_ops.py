from __future__ import annotations

from src.marketing_ops.auth import demo_identity
from src.marketing_ops.campaign_ops import campaign_checklist, campaign_tasks, create_campaign_tasks
from src.marketing_ops.config import MarketingSettings
from src.marketing_ops.models import Role
from src.marketing_ops.store import OperationalStore


def test_campaign_checklist_adds_only_selected_channel_work() -> None:
    campaign = {
        "id": "campaign-1",
        "name": "Designer drop",
        "start_date": "2026-09-01",
        "channels": ["Klaviyo", "Blog / SEO"],
    }
    rows = campaign_checklist(campaign)
    channels = {row["channel"] for row in rows}
    assert "Klaviyo" in channels
    assert "Blog / SEO" in channels
    assert "Google Ads" not in channels
    assert all(row["due_date"] for row in rows)


def test_campaign_checklist_creation_is_idempotent(tmp_path) -> None:
    store = OperationalStore(tmp_path / "campaign.sqlite3", seed_demo=False)
    identity = demo_identity(MarketingSettings(), Role.ADMINISTRATOR)
    campaign_id = store.create_campaign(
        identity,
        name="September drop",
        objective="Sell approved available inventory",
        audience="Existing subscribers",
        geography="Hong Kong",
        owner=identity.display_name,
        channels=["Klaviyo"],
        start_date="2026-09-01",
    )
    campaign = next(row for row in store.list_campaigns() if row["id"] == campaign_id)
    first = create_campaign_tasks(store, identity, campaign)
    second = create_campaign_tasks(store, identity, campaign)
    assert len(set(first)) == len(first)
    assert set(second) == set(first)
    assert len(campaign_tasks(store, campaign_id)) == len(first)
