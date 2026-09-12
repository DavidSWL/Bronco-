"""Trade-in value projection.

The trade vehicle is paid off, so its full value is available as trade
equity. We project it forward to the December target date with a simple
compounding monthly depreciation estimate.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from . import config


def months_between(start: date, end: date) -> float:
    return (end.year - start.year) * 12 + (end.month - start.month) + (end.day - start.day) / 30.0


def project_value(as_of: date, trade_in: dict[str, Any]) -> float:
    baseline_value = trade_in["baseline_value"]
    baseline_date = date.fromisoformat(trade_in["baseline_date"])
    rate = trade_in["monthly_depreciation_rate"]

    months = max(months_between(baseline_date, as_of), 0.0)
    return baseline_value * ((1 - rate) ** months)


def projection_to_target(trade_in: dict[str, Any], target: date = config.TARGET_BUY_DATE) -> dict[str, Any]:
    today = date.today()
    value_today = project_value(today, trade_in)
    value_at_target = project_value(target, trade_in)
    return {
        "baseline_value": trade_in["baseline_value"],
        "baseline_date": trade_in["baseline_date"],
        "as_of_today": round(value_today),
        "projected_at_target": round(value_at_target),
        "target_date": target.isoformat(),
        "estimated_drift": round(value_at_target - trade_in["baseline_value"]),
    }
