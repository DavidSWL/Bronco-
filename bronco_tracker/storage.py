"""JSON-backed storage for tracked Bronco listings.

Deliberately dependency-free (stdlib only) so the tracker can run in any
fresh environment without an install step.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any

from . import config


def _today() -> str:
    return date.today().isoformat()


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return json.loads(content) if content else {}


def _save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def load_listings() -> dict[str, dict[str, Any]]:
    return _load(config.LISTINGS_FILE)


def save_listings(listings: dict[str, dict[str, Any]]) -> None:
    _save(config.LISTINGS_FILE, listings)


def upsert_listing(listing_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Add a new listing or update an existing one, tracking price history,
    first/last seen dates, and status. Returns the stored record.
    """
    listings = load_listings()
    today = _today()
    price = fields.get("price")

    existing = listings.get(listing_id)
    if existing is None:
        record = {
            **fields,
            "id": listing_id,
            "first_seen": today,
            "last_seen": today,
            "status": "active",
            "price_history": [{"date": today, "price": price}] if price is not None else [],
        }
    else:
        record = {**existing, **fields, "id": listing_id, "last_seen": today}
        history = list(existing.get("price_history", []))
        if price is not None and (not history or history[-1]["price"] != price):
            history.append({"date": today, "price": price})
        record["price_history"] = history
        record["status"] = "active"

    listings[listing_id] = record
    save_listings(listings)
    return record


def mark_removed(listing_id: str, status: str = "removed") -> None:
    """Mark a listing sold/removed instead of deleting it, so it still
    counts toward market trend history.
    """
    listings = load_listings()
    if listing_id in listings:
        listings[listing_id]["status"] = status
        listings[listing_id]["last_seen"] = _today()
        save_listings(listings)


def sweep_missing(seen_ids: set[str]) -> list[str]:
    """Mark any currently-active listing not present in `seen_ids` as
    removed/sold. Call this once per data-collection sweep after upserting
    everything that was found. Returns the list of ids marked removed.
    """
    listings = load_listings()
    changed = []
    for listing_id, record in listings.items():
        if record.get("status") == "active" and listing_id not in seen_ids:
            record["status"] = "removed"
            record["last_seen"] = _today()
            changed.append(listing_id)
    if changed:
        save_listings(listings)
    return changed


def days_on_market(record: dict[str, Any]) -> int:
    first_seen = datetime.fromisoformat(record["first_seen"]).date()
    end = (
        date.today()
        if record.get("status") == "active"
        else datetime.fromisoformat(record["last_seen"]).date()
    )
    return (end - first_seen).days


def load_trade_in() -> dict[str, Any]:
    data = _load(config.TRADE_IN_FILE)
    if not data:
        data = {
            "baseline_value": config.TRADE_IN_BASELINE_VALUE,
            "baseline_date": config.TRADE_IN_BASELINE_DATE.isoformat(),
            "monthly_depreciation_rate": config.MONTHLY_DEPRECIATION_RATE,
            "history": [],
        }
        _save(config.TRADE_IN_FILE, data)
    return data
