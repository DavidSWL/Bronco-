"""Generate the human-readable markdown report from tracked data."""
from __future__ import annotations

from datetime import date

from . import config, deals, storage, trade_in


def _fmt_money(n) -> str:
    return f"${n:,.0f}" if n is not None else "n/a"


def build_report() -> str:
    listings = storage.load_listings()
    ranked = deals.rank_deals(listings)
    trends = deals.trend_summary(listings)
    ti = trade_in.projection_to_target(storage.load_trade_in())

    days_left = (config.TARGET_BUY_DATE - date.today()).days
    lines: list[str] = []

    lines.append("# Bronco Deal Tracker")
    lines.append("")
    lines.append(f"_Last updated: {date.today().isoformat()}_")
    lines.append("")
    lines.append(
        f"**{days_left} days** until target buy date "
        f"({config.TARGET_BUY_DATE.isoformat()})."
    )
    lines.append("")

    lines.append("## Trade-in equity")
    lines.append("")
    lines.append(f"- Baseline value ({ti['baseline_date']}, paid off): {_fmt_money(ti['baseline_value'])}")
    lines.append(f"- Estimated value today: {_fmt_money(ti['as_of_today'])}")
    lines.append(
        f"- Projected value at target date ({ti['target_date']}): "
        f"{_fmt_money(ti['projected_at_target'])} "
        f"({'-' if ti['estimated_drift'] < 0 else '+'}{_fmt_money(abs(ti['estimated_drift']))})"
    )
    lines.append(
        "- _This is a planning estimate (compounding monthly depreciation), "
        "not an appraisal — get a real KBB/Carvana/CarMax quote close to purchase time._"
    )
    lines.append("")

    lines.append("## Market snapshot")
    lines.append("")
    if trends["count"] == 0:
        lines.append("_No active listings tracked yet._")
    else:
        lines.append(f"- Active listings tracked: {trends['count']}")
        lines.append(
            f"- Price range: {_fmt_money(trends['min_price'])} - {_fmt_money(trends['max_price'])}"
            f" (avg {_fmt_money(trends['avg_price'])})"
        )
        lines.append(f"- Average days on market: {trends['avg_days_on_market']}")
        lines.append(
            f"- Stale listings ({config.STALE_DAYS_ON_MARKET}+ days, good negotiating leverage): "
            f"{trends['stale_count']}"
        )
        lines.append(f"- Sold/removed since tracking began: {trends['sold_or_removed_count']}")
        lines.append("")
        lines.append("**Average price by trim:**")
        for trim, avg in sorted(trends["avg_price_by_trim"].items(), key=lambda kv: kv[1]):
            lines.append(f"- {trim}: {_fmt_money(avg)}")
    lines.append("")

    lines.append("## Ranked deals (best first)")
    lines.append("")
    if not ranked:
        lines.append("_Nothing tracked yet. Add listings as you find them._")
    else:
        lines.append(
            "| Score | Trim | Color | Price | vs peer avg | Days on market | Price drop | Dealer | Link |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in ranked:
            stale_flag = " 🕓" if r["is_stale"] else ""
            drop_flag = f"-{_fmt_money(r['price_drop'])}" if r["price_drop"] > 0 else "—"
            lines.append(
                f"| {r['score']} | {r.get('trim', '?')} | {r.get('color_exterior', '?')} | "
                f"{_fmt_money(r.get('price'))} | {r['pct_below_peer_avg']}% | "
                f"{r['days_on_market']}{stale_flag} | {drop_flag} | "
                f"{r.get('dealer', '?')} | [listing]({r.get('url', '')}) |"
            )
    lines.append("")
    lines.append(
        "_Score blends price-vs-peer-average, days on market, and observed price drops. "
        "🕓 = stale listing (21+ days), typically more negotiable._"
    )
    lines.append("")

    return "\n".join(lines)


def write_report() -> str:
    text = build_report()
    with open(config.REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    return text
