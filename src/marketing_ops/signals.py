from __future__ import annotations

from typing import Any, Mapping

from .models import DataMode, Responsibility, Severity, Signal


def _signal(
    rule_id: str,
    title: str,
    description: str,
    why: str,
    evidence: str,
    action: str,
    playbook: tuple[str, ...],
    success: str,
    source: str,
    entity: str,
    severity: Severity,
    confidence: float,
    owner: Responsibility,
    *,
    mode: DataMode = DataMode.FIXTURE,
    metadata: dict[str, Any] | None = None,
) -> Signal:
    return Signal(
        rule_id=rule_id,
        rule_version="1.0",
        title=title,
        description=description,
        why_it_matters=why,
        evidence=evidence,
        recommended_action=action,
        playbook=playbook,
        success_measure=success,
        source_system=source,
        source_entity=entity,
        severity=severity,
        confidence=confidence,
        data_period="1–31 July 2026",
        data_freshness="Agency fixture prepared 6 August 2026",
        owner_role=owner,
        deduplication_key=f"{rule_id}:2026-07:{entity}",
        data_mode=mode,
        metadata=metadata or {},
    )


def detect_business_signals(dataset: Mapping[str, Any]) -> list[Signal]:
    signals: list[Signal] = []
    reconciliation = dataset.get("reconciliation") or []
    store_gap = next((row for row in reconciliation if row.get("Metric") == "Store/location revenue sum"), None)
    if store_gap and store_gap.get("Status") == "Review required":
        difference = float(store_gap.get("Absolute difference") or 0)
        signals.append(
            _signal(
                "DATA.REVENUE_RECONCILIATION_GAP",
                "Resolve the HK$30,146.56 store-revenue gap",
                "The store/location rows do not reconcile to the executive commerce-revenue headline.",
                "Marketing decisions are unreliable when the commerce total and location detail disagree.",
                f"Store sum minus headline revenue = HK${difference:,.2f}; five headline orders are also not allocated in the store table.",
                "Confirm the location mapping, excluded/test order rules, refunds, and report filters before accepting July as a baseline.",
                (
                    "Export July order-level Shopify data with location, channel, refunds, and test/cancel state.",
                    "Recreate both headline and store filters from the same order set.",
                    "Document every exclusion and update the metric dictionary.",
                    "Mark the reconciliation reviewed only after the difference is explained.",
                ),
                "Absolute unexplained difference is at or below HK$1 and order allocation matches the headline.",
                "Shopify / agency report",
                "July 2026 commerce reconciliation",
                Severity.CRITICAL,
                0.99,
                Responsibility.DATA_OWNER,
                metadata={"difference_hkd": difference},
            )
        )

    channel_gap = next((row for row in reconciliation if row.get("Metric") == "Revenue represented by channel chart"), None)
    if channel_gap and channel_gap.get("Status") == "Review required":
        represented = float(channel_gap.get("New platform") or 0)
        headline = float(channel_gap.get("Agency report") or 0)
        coverage = 100 * represented / headline if headline else 0
        signals.append(
            _signal(
                "DATA.CHANNEL_ATTRIBUTION_NOT_RECONCILED",
                "Stop presenting the channel chart as a complete revenue split",
                "The displayed channel rows cover only part of commerce revenue and use attribution windows that can overlap.",
                "Adding or comparing these rows as mutually exclusive channels can overstate contribution and misdirect budget.",
                f"Email, Google Ads, Direct and Meta total HKD {represented:,.2f}, or {coverage:.2f}% of the HKD {headline:,.2f} headline revenue; the report states 90 days for email and seven days for Meta.",
                "Rename the visual as attribution views, show the window beside every value, and add a clearly labelled unrepresented share without treating it as a fifth channel.",
                (
                    "Confirm the source and configured window for every channel row.",
                    "Keep Shopify/POS commerce revenue as the booked source of truth.",
                    "Display platform views separately and state that they can overlap.",
                    "Reconcile the represented share before approving the monthly report.",
                ),
                "Every channel value has a source/window label and the management report contains no mutually exclusive channel-sum claim.",
                "Agency report / attribution layer",
                "July 2026 revenue-by-channel chart",
                Severity.CRITICAL,
                0.99,
                Responsibility.DATA_OWNER,
                metadata={"represented_hkd": represented, "headline_hkd": headline, "coverage_pct": coverage},
            )
        )

    for opportunity in dataset.get("seo_opportunities") or []:
        if float(opportunity.get("score") or 0) < 78:
            continue
        signals.append(
            _signal(
                "SEO.HIGH_IMPRESSIONS_LOW_CTR",
                f"Close the click-through gap: {opportunity['query']}",
                "A page receives meaningful Google visibility but captures too few clicks for its position.",
                "Improving the snippet can create incremental qualified traffic without increasing ad spend.",
                f"{opportunity['impressions']:,} impressions, {opportunity['clicks']:,} clicks, {opportunity['ctr']:.2f}% CTR, average position {opportunity['position']:.1f}; transparent opportunity score {opportunity['score']:.1f}/100.",
                opportunity["action"],
                (
                    "Verify the exact Search Console query/page pair and current snippet.",
                    "Draft two title and description options grounded in the page content.",
                    "Check current HULA inventory and internal links.",
                    "Request brand/SEO approval; do not publish automatically.",
                    "Measure CTR and qualified sessions after 14 and 30 days.",
                ),
                "CTR improves by at least 0.20 percentage points without a material ranking decline.",
                "Google Search Console",
                opportunity["page"],
                Severity.HIGH,
                0.92,
                Responsibility.MARKETING,
                metadata={"factor_contributions": opportunity.get("factor_contributions"), "score": opportunity.get("score")},
            )
        )

    for campaign in dataset.get("meta_campaigns") or []:
        if float(campaign.get("frequency") or 0) >= 3.5 and float(campaign.get("ctr") or 0) < 0.8:
            signals.append(
                _signal(
                    "META.CREATIVE_FATIGUE",
                    f"Review creative fatigue in {campaign['campaign']}",
                    "The same audience has seen the creative repeatedly while click-through and purchases are weak.",
                    "Continued spend can waste budget and damage response before new creative is tested.",
                    f"Frequency {campaign['frequency']:.2f}, CTR {campaign['ctr']:.2f}%, spend HK${campaign['spend']:,.0f}, purchases {campaign['purchases']} in the fixture.",
                    "Prepare a replacement creative concept and ask the paid-media specialist to review audience overlap, landing page, and rotation.",
                    (
                        "Confirm the values in Meta Ads Manager using the account attribution setting.",
                        "Check whether the landing product/collection is available.",
                        "Prepare at least two new creative angles and a measurement plan.",
                        "Request paid-media review before any campaign change.",
                    ),
                    "Frequency falls below 3.5 or CTR recovers above 1.0% with purchase tracking healthy.",
                    "Meta Ads",
                    campaign["campaign"],
                    Severity.HIGH,
                    0.90,
                    Responsibility.PAID_MEDIA_SPECIALIST,
                    metadata={"frequency": campaign["frequency"], "ctr": campaign["ctr"], "spend": campaign["spend"]},
                )
            )

    for campaign in dataset.get("google_campaigns") or []:
        if float(campaign.get("budget_pacing_pct") or 0) > 115 and float(campaign.get("roas") or 0) < 3:
            signals.append(
                _signal(
                    "GOOGLE_ADS.OVER_PACING_LOW_ROAS",
                    f"Review pacing and efficiency: {campaign['campaign']}",
                    "The campaign is projected to exceed budget while returning below the fixture efficiency threshold.",
                    "A human review can prevent waste, but conversion tracking and search-term evidence must be checked before changing budget.",
                    f"Budget pacing {campaign['budget_pacing_pct']}%, spend HK${campaign['spend']:,.2f}, ROAS {campaign['roas']:.2f}x, purchases {campaign['purchases']}.",
                    "Ask the paid-media specialist to review search terms, negatives, landing-page fit, and conversion health; no automatic budget change.",
                    (
                        "Verify final Google Ads cost and conversion values.",
                        "Separate relevant competitor demand from wasted terms.",
                        "Check the landing page and inventory.",
                        "Prepare an approved proposal within budget guardrails.",
                    ),
                    "Pacing returns to 90–110% and ROAS meets the agreed campaign target.",
                    "Google Ads",
                    campaign["campaign"],
                    Severity.HIGH,
                    0.88,
                    Responsibility.PAID_MEDIA_SPECIALIST,
                    metadata={"budget_pacing_pct": campaign["budget_pacing_pct"], "roas": campaign["roas"]},
                )
            )

    unavailable = [item for item in dataset.get("catalogue_issues") or [] if "unavailable" in str(item.get("issue", "")).lower()]
    for item in unavailable:
        signals.append(
            _signal(
                "COMMERCE.UNAVAILABLE_PRODUCT_PROMOTED",
                f"Stop promoting unavailable inventory: {item['product']}",
                "A fixture catalogue check links an unavailable one-off product to active marketing.",
                "Luxury resale inventory is often unique; spend and customer attention should move quickly to available alternatives.",
                f"Inventory state: {item['inventory']}; issue: {item['issue']}; fixture traffic: {item['traffic']:,}.",
                item["recommendation"],
                (
                    "Verify live Shopify inventory and the ad/article destination.",
                    "Identify an available collection or equivalent product.",
                    "Prepare a paid-media/content change proposal.",
                    "Verify the destination after an approved human change.",
                ),
                "No active ad or high-traffic article points to an unavailable product URL.",
                "Shopify + paid media",
                item["product"],
                Severity.CRITICAL,
                0.95,
                Responsibility.PAID_MEDIA_SPECIALIST,
            )
        )

    for location in dataset.get("gbp") or []:
        if int(location.get("unanswered") or 0) > 0:
            signals.append(
                _signal(
                    "GBP.UNANSWERED_REVIEWS",
                    f"Draft responses for {location['location']} reviews",
                    "The fixture indicates customer reviews are awaiting a response.",
                    "Timely, thoughtful responses support trust and local-store visibility.",
                    f"{location['unanswered']} unanswered review(s), {location['rating']:.1f} rating across {location['reviews']} reviews.",
                    "Open the verified reviews, draft individual responses, and request approval before posting.",
                    (
                        "Verify the live review text and whether a response already exists.",
                        "Draft a specific, non-defensive response without exposing customer information.",
                        "Escalate service or legal concerns internally.",
                        "Obtain approval before any public reply.",
                    ),
                    "All eligible reviews receive an approved response within three business days.",
                    "Google Business Profile",
                    location["location"],
                    Severity.MEDIUM,
                    0.85,
                    Responsibility.MARKETING,
                )
            )
    return sorted(signals, key=lambda item: ({Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}[item.severity], -item.confidence))


def integration_health_signals(
    states: Mapping[str, str],
    *,
    data_mode: DataMode = DataMode.DEMO,
) -> list[Signal]:
    signals: list[Signal] = []
    for provider, state in states.items():
        if state not in {"Error", "Stale", "Permission insufficient"}:
            continue
        signals.append(
            _signal(
                "DATA.INTEGRATION_HEALTH",
                f"Restore {provider} data health",
                f"The integration is currently marked {state}.",
                "Decisions based on stale or failed data can misallocate spend or hide customer-impacting issues.",
                f"Integration health state: {state}.",
                "Use the connection test, verify permissions and API version, then queue a controlled resync.",
                (
                    "Open Integrations & Health and read the redacted error.",
                    "Ask the credential owner to verify access without sharing secrets in chat.",
                    "Run the explicit connection test.",
                    "Queue a backfill only after the connection is healthy.",
                ),
                "The connector returns Healthy and a reconciled sync completes.",
                provider,
                provider,
                Severity.CRITICAL,
                0.98,
                Responsibility.ADMINISTRATOR,
                mode=data_mode,
            )
        )
    return signals
