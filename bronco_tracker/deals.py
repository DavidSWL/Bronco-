"""Deal scoring and market trend analysis over tracked listings."""
from __future__ import annotations

from statistics import mean
from typing import Any

from . import config, storage


def active(listings: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in listings.values() if r.get("status") == "active"]


def peer_group(listings: list[dict[str, Any]], record: dict[str, Any]) -> list[dict[str, Any]]:
    """Listings of the same trim, falling back to all active listings if
    there are too few same-trim peers to be a meaningful average.
    """
    same_trim = [r for r in listings if r.get("trim") == record.get("trim")]
    return same_trim if len(same_trim) >= 3 else listings


def price_drop(record: dict[str, Any]) -> int:
    history = record.get("price_history", [])
    if len(history) < 2:
        return 0
    return history[0]["price"] - history[-1]["price"]


def score(record: dict[str, Any], all_active: list[dict[str, Any]]) -> dict[str, Any]:
    """Score one listing. Higher is a better deal."""
    peers = [r for r in peer_group(all_active, record) if r["id"] != record["id"]]
    price = record.get("price") or 0
    avg_peer_price = mean(r["price"] for r in peers) if peers else price

    pct_below_avg = ((avg_peer_price - price) / avg_peer_price * 100) if avg_peer_price else 0.0
    dom = storage.days_on_market(record)
    drop = price_drop(record)

    # Weighted heuristic: price relative to peers matters most; a stale
    # listing (negotiating leverage) and any observed price cut add to it.
    total = pct_below_avg * 1.0
    total += min(dom / config.STALE_DAYS_ON_MARKET, 2.0) * 3.0
    total += (drop / 1000) * 2.0 if drop > 0 else 0

    return {
        "id": record["id"],
        "score": round(total, 1),
        "pct_below_peer_avg": round(pct_below_avg, 1),
        "peer_avg_price": round(avg_peer_price),
        "days_on_market": dom,
        "price_drop": drop,
        "is_stale": dom >= config.STALE_DAYS_ON_MARKET,
    }


def rank_deals(listings: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return active listings joined with their deal score, best first."""
    listings = listings if listings is not None else storage.load_listings()
    live = active(listings)
    scored = [{**listings[r["id"]], **score(r, live)} for r in live]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored


def inactive_summaries(listings: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Sold/removed listings, newest-gone first, with days-on-market and
    price-drop computed the same way as active ones.
    """
    listings = listings if listings is not None else storage.load_listings()
    out = [
        {**r, "days_on_market": storage.days_on_market(r), "price_drop": price_drop(r)}
        for r in listings.values()
        if r.get("status") != "active"
    ]
    out.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
    return out


def trend_summary(listings: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    listings = listings if listings is not None else storage.load_listings()
    live = active(listings)
    if not live:
        return {"count": 0}

    prices = [r["price"] for r in live if r.get("price") is not None]
    dom_list = [storage.days_on_market(r) for r in live]
    by_trim: dict[str, list[int]] = {}
    for r in live:
        by_trim.setdefault(r.get("trim", "Unknown"), []).append(r["price"])

    sold_or_removed = [r for r in listings.values() if r.get("status") != "active"]

    return {
        "count": len(live),
        "avg_price": round(mean(prices)) if prices else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_days_on_market": round(mean(dom_list), 1) if dom_list else None,
        "avg_price_by_trim": {t: round(mean(p)) for t, p in by_trim.items()},
        "stale_count": sum(1 for d in dom_list if d >= config.STALE_DAYS_ON_MARKET),
        "sold_or_removed_count": len(sold_or_removed),
    }
