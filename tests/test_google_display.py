from __future__ import annotations

from src.analysis.freshness import google_display_series, validate_series
from src.analysis.trends import score_google_series, score_google_windows


def test_anchor_calibration_can_exceed_100_but_display_never_does() -> None:
    points = [
        {
            "date": f"2026-07-{index:02d}",
            "value": calibrated,
            "raw_value": raw,
        }
        for index, (calibrated, raw) in enumerate(
            [(120, 40), (150, 50), (180, 60), (210, 70), (225, 75), (240, 80)],
            1,
        )
    ]
    rows = score_google_series({"ballet flats": points})
    assert max(point["value"] for point in rows[0]["series"]) > 100
    assert max(point["value"] for point in rows[0]["display_series"]) <= 100


def test_low_resolution_plateau_is_not_charted() -> None:
    points = [
        {"date": f"2026-07-{index:02d}", "value": value, "raw_value": value}
        for index, value in enumerate([10, 10, 10, 10, 10, 30, 30, 30], 1)
    ]
    _, quality = validate_series(points)
    display, display_quality = google_display_series(points)
    assert quality["chart_ready"] is False
    assert display_quality["excessive_plateau"] is True
    assert display == []


def test_calibrated_legacy_values_without_raw_index_are_withheld() -> None:
    points = [
        {"date": f"2026-07-{index:02d}", "value": value}
        for index, value in enumerate([100, 125, 150, 175, 200, 225], 1)
    ]
    display, quality = google_display_series(points)
    assert quality["display_out_of_range"] is True
    assert display == []


def test_recent_chart_survives_when_annual_context_request_fails() -> None:
    recent = {
        "drop waist dress": [
            {
                "date": f"2026-07-{index + 1:02d}",
                "value": value,
                "raw_value": value,
            }
            for index, value in enumerate(
                [
                    12, 14, 18, 16, 21, 24, 20, 25, 28, 31,
                    29, 33, 37, 35, 41, 44, 39, 47, 50, 46,
                    54, 58, 55, 62, 66, 64, 71, 74,
                ]
            )
        ]
    }

    row = score_google_windows({}, recent)[0]

    assert row["query"] == "drop waist dress"
    assert row["google_context_score"] is None
    assert row["chart_ready"] is False
    assert row["recent_chart_ready"] is True
    assert len(row["recent_display_series"]) == 28
