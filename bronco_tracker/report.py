"""Generate the human-readable report from tracked data (markdown + HTML)."""
from __future__ import annotations

import html as html_escape
from datetime import date
from typing import Any

from . import budget, config, deals, storage, trade_in


def _fmt_money(n) -> str:
    return f"${n:,.0f}" if n is not None else "n/a"


def _gather() -> dict[str, Any]:
    listings = storage.load_listings()
    ti = trade_in.projection_to_target(storage.load_trade_in())
    # Use the trade-in's value projected to the target buy date, since
    # that's roughly when the trade actually happens.
    trade_in_value = ti["projected_at_target"]

    ranked = deals.rank_deals(listings)
    for r in ranked:
        upgraded = budget.is_upgraded(r)
        r["budget"] = budget.estimate_out_of_pocket(r.get("price"), r.get("trim"), trade_in_value, upgraded=upgraded)
        r["email"] = budget.email_template(r, trade_in_value)

    upgraded_picks = [r for r in ranked if r["budget"]["upgraded"]]

    return {
        "ranked": ranked,
        "upgraded_picks": upgraded_picks,
        "sold": deals.inactive_summaries(listings),
        "trends": deals.trend_summary(listings),
        "ti": ti,
        "trade_in_value": trade_in_value,
        "days_left": (config.TARGET_BUY_DATE - date.today()).days,
        "today": date.today().isoformat(),
    }


def build_report() -> str:
    data = _gather()
    ranked, trends, ti = data["ranked"], data["trends"], data["ti"]
    lines: list[str] = []

    lines.append("# Bronco Deal Tracker")
    lines.append("")
    lines.append(f"_Last updated: {data['today']}_")
    lines.append("")
    lines.append(
        f"**{data['days_left']} days** until target buy date "
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
        lines.append("**Price range by trim (active listings):**")
        for trim, stats in sorted(trends["price_by_trim"].items(), key=lambda kv: kv[1]["avg"]):
            lines.append(
                f"- {trim}: {_fmt_money(stats['low'])} - {_fmt_money(stats['high'])} "
                f"(avg {_fmt_money(stats['avg'])}, n={stats['count']})"
            )
        if trends["sold_price_by_trim"]:
            lines.append("")
            lines.append(f"**What sold, by trim** ({trends['sold_count']} confirmed sales tracked):")
            for trim, stats in sorted(trends["sold_price_by_trim"].items(), key=lambda kv: kv[1]["avg"]):
                lines.append(
                    f"- {trim}: sold {_fmt_money(stats['low'])} - {_fmt_money(stats['high'])} "
                    f"(avg {_fmt_money(stats['avg'])}, n={stats['count']})"
                )
    lines.append("")

    if data["upgraded_picks"]:
        lines.append("## Upgraded picks (fog lights + 360 camera)")
        lines.append("")
        lines.append(
            f"These have the Lux Package (360-degree camera) plus fog lights, so they get "
            f"{_fmt_money(config.UPGRADED_OOP_ALLOWANCE)} more budget room than a standard listing."
        )
        lines.append("")
        for r in data["upgraded_picks"]:
            b = r["budget"]
            budget_note = "in budget" if b["within_budget"] else f"+{_fmt_money(b['over_by'])} over"
            lines.append(
                f"- {r.get('trim')} · {r.get('color_exterior')} — {_fmt_money(r.get('price'))} sticker, "
                f"{_fmt_money(b['out_of_pocket'])} cash/finance ({budget_note}) "
                f"at {r.get('dealer')} — [listing]({r.get('url', '')})"
            )
        lines.append("")

    lines.append("## Listings, lowest price first")
    lines.append("")
    lines.append(
        f"Out-of-pocket assumes your trade-in is worth {_fmt_money(data['trade_in_value'])} at purchase "
        f"time and California's {config.SALES_TAX_RATE:.2%} sales tax (CA taxes the full price - the "
        f"trade-in doesn't reduce the taxable amount). Budget: {_fmt_money(config.OOP_CAP_STANDARD)} for "
        f"Big Bend/Outer Banks, up to {_fmt_money(config.OOP_CAP_HIGHER_TRIM)} for a higher trim. "
        f"(Score column ranks by deal quality, not price - see the tips section for how to use it.)"
    )
    lines.append("")
    if not ranked:
        lines.append("_Nothing tracked yet. Add listings as you find them._")
    else:
        by_price = sorted(ranked, key=lambda r: r.get("price") or 0)
        lines.append(
            "| Price | Trim | Color | Score | Est. cash/finance | Budget | vs peer avg | Days on market | Price drop | Dealer | Link |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in by_price:
            stale_flag = " 🕓" if r["is_stale"] else ""
            drop_flag = f"-{_fmt_money(r['price_drop'])}" if r["price_drop"] > 0 else "—"
            b = r["budget"]
            budget_flag = "✅ in budget" if b["within_budget"] else f"⚠️ +{_fmt_money(b['over_by'])}"
            lines.append(
                f"| {_fmt_money(r.get('price'))} | {r.get('trim', '?')} | {r.get('color_exterior', '?')} | "
                f"{r['score']} | {_fmt_money(b['out_of_pocket'])} | {budget_flag} | "
                f"{r['pct_below_peer_avg']}% | "
                f"{r['days_on_market']}{stale_flag} | {drop_flag} | "
                f"{r.get('dealer', '?')} | [listing]({r.get('url', '')}) |"
            )
    lines.append("")
    lines.append(
        "_Score blends price-vs-peer-average, days on market, and observed price drops. "
        "🕓 = stale listing (21+ days), typically more negotiable._"
    )
    lines.append("")

    lines.append("## Getting the best deal")
    lines.append("")
    for tip in budget.NEGOTIATION_TIPS:
        lines.append(f"- {tip}")
    lines.append("")

    return "\n".join(lines)


def _e(value: Any) -> str:
    return html_escape.escape(str(value)) if value is not None else "?"


def build_html_report() -> str:
    data = _gather()
    ranked, trends, ti = data["ranked"], data["trends"], data["ti"]
    upgraded_picks = data["upgraded_picks"]

    if trends["count"] == 0:
        market_html = "<p class='muted'>No active listings tracked yet.</p>"
    else:
        trim_rows = "".join(
            f"<li>{_e(trim)}: <strong>{_fmt_money(s['low'])}&ndash;{_fmt_money(s['high'])}</strong> "
            f"(avg {_fmt_money(s['avg'])}, n={s['count']})</li>"
            for trim, s in sorted(trends["price_by_trim"].items(), key=lambda kv: kv[1]["avg"])
        )
        sold_rows = "".join(
            f"<li>{_e(trim)}: sold <strong>{_fmt_money(s['low'])}&ndash;{_fmt_money(s['high'])}</strong> "
            f"(avg {_fmt_money(s['avg'])}, n={s['count']})</li>"
            for trim, s in sorted(trends["sold_price_by_trim"].items(), key=lambda kv: kv[1]["avg"])
        )
        sold_html = (
            f"<p><strong>What sold, by trim</strong> ({trends['sold_count']} confirmed):</p><ul>{sold_rows}</ul>"
            if trends["sold_price_by_trim"] else ""
        )
        market_html = f"""
        <div class="stat-grid">
          <div class="stat"><span class="stat-value">{trends['count']}</span><span class="stat-label">active listings</span></div>
          <div class="stat"><span class="stat-value">{_fmt_money(trends['avg_price'])}</span><span class="stat-label">avg price</span></div>
          <div class="stat"><span class="stat-value">{trends['avg_days_on_market']}</span><span class="stat-label">avg days on market</span></div>
          <div class="stat"><span class="stat-value">{trends['stale_count']}</span><span class="stat-label">stale (21+ days)</span></div>
        </div>
        <p>Price range: {_fmt_money(trends['min_price'])} &ndash; {_fmt_money(trends['max_price'])}.
        Sold/removed since tracking began: {trends['sold_or_removed_count']}.</p>
        <p><strong>Price range by trim (active):</strong></p>
        <ul>{trim_rows}</ul>
        {sold_html}
        """

    if not ranked:
        deals_html = "<p class='muted'>Nothing tracked yet. Add listings as you find them.</p>"
    else:
        rows = []
        for r in sorted(ranked, key=lambda r: r.get("price") or 0):
            stale = " <span class='badge'>stale</span>" if r["is_stale"] else ""
            drop = f"-{_fmt_money(r['price_drop'])}" if r["price_drop"] > 0 else "&mdash;"
            url = _e(r.get("url", "")) if r.get("url") else ""
            link = f"<a href='{url}' target='_blank' rel='noopener'>view</a>" if url else "&mdash;"
            b = r["budget"]
            budget_badge = (
                "<span class='badge good'>in budget</span>" if b["within_budget"]
                else f"<span class='badge over'>+{_fmt_money(b['over_by'])}</span>"
            )
            rows.append(f"""
              <tr>
                <td>{_fmt_money(r.get('price'))}</td>
                <td>{_e(r.get('trim'))}</td>
                <td>{_e(r.get('color_exterior'))}</td>
                <td class="score">{r['score']}</td>
                <td>{_fmt_money(b['out_of_pocket'])}</td>
                <td>{budget_badge}</td>
                <td>{r['pct_below_peer_avg']}%</td>
                <td>{r['days_on_market']}{stale}</td>
                <td>{drop}</td>
                <td>{_e(r.get('dealer'))}</td>
                <td>{link}</td>
              </tr>""")
        deals_html = f"""
        <p class="muted">Out-of-pocket assumes a {_fmt_money(data['trade_in_value'])} trade-in and CA's
        {config.SALES_TAX_RATE:.2%} sales tax (CA taxes the full price, trade-in doesn't reduce it).
        Budget: {_fmt_money(config.OOP_CAP_STANDARD)} standard trim, up to {_fmt_money(config.OOP_CAP_HIGHER_TRIM)} for a higher trim.</p>
        <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Price</th><th>Trim</th><th>Color</th><th>Score</th><th>Est. cash/finance</th><th>Budget</th>
            <th>vs peer avg</th><th>Days on market</th><th>Price drop</th><th>Dealer</th><th></th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        </div>
        """

    drift_sign = "-" if ti["estimated_drift"] < 0 else "+"

    if not upgraded_picks:
        upgraded_html = ""
    else:
        up_rows = []
        for r in upgraded_picks:
            b = r["budget"]
            badge = (
                "<span class='badge good'>in budget</span>" if b["within_budget"]
                else f"<span class='badge over'>+{_fmt_money(b['over_by'])}</span>"
            )
            url = _e(r.get("url", "")) if r.get("url") else ""
            link = f"<a href='{url}' target='_blank' rel='noopener'>view</a>" if url else "&mdash;"
            up_rows.append(
                f"<li>{_e(r.get('trim'))} &middot; {_e(r.get('color_exterior'))} &mdash; "
                f"{_fmt_money(r.get('price'))} sticker / {_fmt_money(b['out_of_pocket'])} cash-finance "
                f"{badge} at {_e(r.get('dealer'))} &mdash; {link}</li>"
            )
        upgraded_html = f"""
        <div class="card">
          <h2>Upgraded picks (fog lights + 360 camera)</h2>
          <p class="muted">Has the Lux Package (360&deg; camera) plus fog lights &mdash;
          {_fmt_money(config.UPGRADED_OOP_ALLOWANCE)} extra budget room vs. a standard listing.</p>
          <ul>{"".join(up_rows)}</ul>
        </div>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bronco Deal Tracker</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #f7f7f5; --card: #ffffff; --text: #1a1a1a; --muted: #6b6b6b;
    --border: #e3e2de; --accent: #b3491f; --accent-bg: #fbeee7;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #161512; --card: #201f1c; --text: #ececea; --muted: #9a9890;
      --border: #35342f; --accent: #ff8a5c; --accent-bg: #3a2419; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px 48px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5;
  }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  h2 {{ font-size: 1.1rem; margin: 0 0 12px; }}
  .muted {{ color: var(--muted); }}
  .updated {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }}
  .countdown {{
    background: var(--accent-bg); color: var(--accent); border-radius: 12px;
    padding: 14px 18px; font-weight: 600; margin-bottom: 24px; display: inline-block;
  }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 20px; margin-bottom: 20px;
  }}
  .stat-grid {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }}
  .stat {{ display: flex; flex-direction: column; min-width: 110px; }}
  .stat-value {{ font-size: 1.4rem; font-weight: 700; }}
  .stat-label {{ color: var(--muted); font-size: 0.8rem; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; }}
  td.score {{ font-weight: 700; }}
  tbody tr:hover {{ background: var(--accent-bg); }}
  .badge {{
    background: var(--accent-bg); color: var(--accent); border-radius: 999px;
    padding: 2px 8px; font-size: 0.72rem; font-weight: 600;
  }}
  .badge.good {{ background: #e2f2e6; color: #2f7d4f; }}
  .badge.over {{ background: #fbeee7; color: #b3491f; }}
  @media (prefers-color-scheme: dark) {{
    .badge.good {{ background: #1e3324; color: #63c088; }}
    .badge.over {{ background: #3c2415; color: #ff8a5c; }}
  }}
  a {{ color: var(--accent); }}
  ul {{ margin: 0; padding-left: 20px; }}
  footer {{ color: var(--muted); font-size: 0.8rem; margin-top: 8px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Bronco Deal Tracker</h1>
  <div class="updated">Last updated: {data['today']}</div>
  <div class="countdown">{data['days_left']} days until target buy date ({config.TARGET_BUY_DATE.isoformat()})</div>

  <div class="card">
    <h2>Trade-in equity</h2>
    <div class="stat-grid">
      <div class="stat"><span class="stat-value">{_fmt_money(ti['baseline_value'])}</span><span class="stat-label">baseline ({ti['baseline_date']}, paid off)</span></div>
      <div class="stat"><span class="stat-value">{_fmt_money(ti['as_of_today'])}</span><span class="stat-label">estimated today</span></div>
      <div class="stat"><span class="stat-value">{_fmt_money(ti['projected_at_target'])}</span><span class="stat-label">projected at {ti['target_date']}</span></div>
      <div class="stat"><span class="stat-value">{drift_sign}{_fmt_money(abs(ti['estimated_drift']))}</span><span class="stat-label">estimated drift</span></div>
    </div>
    <footer>Planning estimate (compounding monthly depreciation), not an appraisal &mdash; get a real KBB/Carvana/CarMax quote close to purchase time.</footer>
  </div>

  <div class="card">
    <h2>Market snapshot</h2>
    {market_html}
  </div>
  {upgraded_html}
  <div class="card">
    <h2>Listings, lowest price first</h2>
    {deals_html}
    <footer>Score blends price-vs-peer-average, days on market, and observed price drops. "stale" = 21+ days on market, typically more negotiable.</footer>
  </div>

  <div class="card">
    <h2>Getting the best deal</h2>
    <ul>{"".join(f"<li>{_e(tip)}</li>" for tip in budget.NEGOTIATION_TIPS)}</ul>
  </div>
</div>
</body>
</html>
"""


def _deal_state(r: dict[str, Any]) -> str:
    """Classify a ranked listing for the stripe/chip treatment."""
    if r["is_stale"]:
        return "watch"
    if r["pct_below_peer_avg"] >= 5 or r["price_drop"] > 0:
        return "good"
    return "neutral"


def _json_for_script(value: Any) -> str:
    """Compact JSON safe to embed inside a <script type="application/json">."""
    import json

    return json.dumps(value, separators=(",", ":")).replace("</", "<\\/")


def build_artifact_html() -> str:
    """Build the artifact-ready fragment: <title> + <style> + body content,
    no <!doctype>/<html>/<head>/<body> - the Artifact host wraps those.

    Gauges and the market snapshot are server-rendered (same every load);
    the ranked-deals section is a small client-side app (search, trim
    filter, sort, expandable price-history sparkline) driven by JSON the
    daily sweep regenerates.
    """
    data = _gather()
    ranked, sold, trends, ti = data["ranked"], data["sold"], data["trends"], data["ti"]

    if trends["count"] == 0:
        market_html = "<p class='muted'>No active listings tracked yet.</p>"
    else:
        trim_chips = "".join(
            f"<div class='trim-row'><span>{_e(trim)}</span>"
            f"<span class='num'>{_fmt_money(s['low'])}&ndash;{_fmt_money(s['high'])} "
            f"<span class='muted small'>(avg {_fmt_money(s['avg'])}, n={s['count']})</span></span></div>"
            for trim, s in sorted(trends["price_by_trim"].items(), key=lambda kv: kv[1]["avg"])
        )
        sold_trim_rows = "".join(
            f"<div class='trim-row'><span>{_e(trim)}</span>"
            f"<span class='num'>{_fmt_money(s['low'])}&ndash;{_fmt_money(s['high'])} "
            f"<span class='muted small'>(avg {_fmt_money(s['avg'])}, n={s['count']})</span></span></div>"
            for trim, s in sorted(trends["sold_price_by_trim"].items(), key=lambda kv: kv[1]["avg"])
        )
        sold_section = (
            f"<h3 class='sub' style='margin-top:16px'>What sold, by trim ({trends['sold_count']} confirmed)</h3>"
            f"<div class='trim-list'>{sold_trim_rows}</div>"
            if trends["sold_price_by_trim"] else ""
        )
        market_html = f"""
        <div class="tile-grid">
          <div class="tile"><span class="tile-value num">{trends['count']}</span><span class="tile-label">active listings</span></div>
          <div class="tile"><span class="tile-value num">{_fmt_money(trends['avg_price'])}</span><span class="tile-label">avg price</span></div>
          <div class="tile"><span class="tile-value num">{trends['avg_days_on_market']}</span><span class="tile-label">avg days on lot</span></div>
          <div class="tile"><span class="tile-value num">{trends['stale_count']}</span><span class="tile-label">stale (21+ days)</span></div>
        </div>
        <div class="range-line">
          <span class="num">{_fmt_money(trends['min_price'])}</span>
          <span class="range-track"><span class="range-fill"></span></span>
          <span class="num">{_fmt_money(trends['max_price'])}</span>
        </div>
        <h3 class="sub">Price range by trim</h3>
        <div class="trim-list">{trim_chips}</div>
        {sold_section}
        """

    trims_available = sorted({r.get("trim") for r in ranked if r.get("trim")})
    trim_chip_buttons = "".join(
        f"<button type=\"button\" class=\"chipbtn\" data-trim=\"{_e(t)}\">{_e(t)}</button>" for t in trims_available
    )

    deals_json = _json_for_script(ranked)
    sold_json = _json_for_script(sold)

    template = """<title>Bronco Watch</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap">
<style>
  :root {
    --bg: #f6f7f6; --surface: #ffffff; --surface-2: #edf0ee;
    --text: #1b1f1c; --muted: #6a706c; --border: #dde1de;
    --accent: #3a6b5e; --accent-soft: #e3edea; --accent-ink: #24443f;
    --good: #3f9d54; --good-soft: #e1f3e3;
    --watch: #9c7a2c; --watch-soft: #f5edd6;
    --over: #b3402c; --over-soft: #f8e3dd;
    --heart: #c1395a;
    --font-display: "Big Shoulders Display", "Arial Narrow", sans-serif;
    --font-body: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #141615; --surface: #1c201d; --surface-2: #20241f;
      --text: #e9ece9; --muted: #949a95; --border: #33382f;
      --accent: #6fae95; --accent-soft: #1f322b; --accent-ink: #bfe3d3;
      --good: #63c088; --good-soft: #1e3324;
      --watch: #d1a94f; --watch-soft: #3a3018;
      --over: #e2735c; --over-soft: #3d241d;
      --heart: #ef7a92;
    }
  }
  :root[data-theme="dark"] {
    --bg: #141615; --surface: #1c201d; --surface-2: #20241f;
    --text: #e9ece9; --muted: #949a95; --border: #33382f;
    --accent: #6fae95; --accent-soft: #1f322b; --accent-ink: #bfe3d3;
    --good: #63c088; --good-soft: #1e3324;
    --watch: #d1a94f; --watch-soft: #3a3018;
    --over: #e2735c; --over-soft: #3d241d;
    --heart: #ef7a92;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--font-body); line-height: 1.5;
  }
  .wrap { max-width: 820px; margin: 0 auto; padding: 28px 18px 56px; }
  .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .muted { color: var(--muted); }
  .small { font-size: 0.8rem; }
  .eyebrow {
    font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.12em;
    font-size: 0.72rem; color: var(--muted); margin: 0 0 6px;
  }
  h1 {
    font-family: var(--font-display); font-weight: 800; font-size: clamp(2.1rem, 8vw, 2.8rem);
    letter-spacing: 0.01em; margin: 0 0 4px; text-wrap: balance;
  }
  h2.sub, h3.sub {
    font-family: var(--font-display); font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; font-size: 1rem; color: var(--muted); margin: 0 0 12px;
  }
  .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 22px; }

  .gauge-strip {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 14px; margin-bottom: 22px;
  }
  .gauge {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 16px 18px;
  }
  .gauge .eyebrow { margin-bottom: 8px; }
  .gauge-value {
    font-family: var(--font-display); font-weight: 800; font-size: 2.1rem;
    color: var(--accent-ink, var(--text)); line-height: 1;
  }
  .gauge-value.hero { color: var(--accent); }
  .gauge-note { margin-top: 6px; font-size: 0.78rem; color: var(--muted); }

  section { margin-bottom: 24px; }
  .panel {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 18px 20px;
  }

  .tile-grid { display: flex; flex-wrap: wrap; gap: 18px; margin-bottom: 14px; }
  .tile { display: flex; flex-direction: column; min-width: 120px; }
  .tile-value { font-size: 1.35rem; font-weight: 600; }
  .tile-label { color: var(--muted); font-size: 0.76rem; margin-top: 2px; }

  .range-line { display: flex; align-items: center; gap: 10px; font-size: 0.85rem; margin: 10px 0 4px; }
  .range-track { flex: 1; height: 4px; background: var(--surface-2); border-radius: 2px; overflow: hidden; }
  .range-fill { display: block; height: 100%; width: 100%; background: var(--accent); opacity: 0.55; }

  .trim-list { border-top: 1px solid var(--border); }
  .trim-row {
    display: flex; justify-content: space-between; padding: 8px 0;
    border-bottom: 1px solid var(--border); font-size: 0.88rem;
  }

  .section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .section-head .sub { margin-bottom: 0; }
  .section-actions { display: flex; align-items: center; gap: 10px; }
  .count-pill {
    font-family: var(--font-mono); font-size: 0.72rem; color: var(--muted);
    background: var(--surface-2); border-radius: 999px; padding: 2px 10px;
  }
  .refresh-btn {
    font-family: var(--font-body); font-size: 0.78rem; font-weight: 500; color: var(--accent);
    background: var(--surface); border: 1px solid var(--border); border-radius: 999px;
    padding: 5px 12px; cursor: pointer;
  }
  .refresh-btn:hover:not(:disabled) { border-color: var(--accent); }
  .refresh-btn:disabled { opacity: 0.55; cursor: default; }
  .refresh-status { margin: 8px 0 0; }

  .controls { display: flex; flex-direction: column; gap: 10px; margin: 14px 0 16px; }
  .controls-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .search-input, .sort-select {
    font-family: var(--font-body); font-size: 0.85rem; color: var(--text);
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 8px 12px;
  }
  .search-input { flex: 1 1 180px; min-width: 0; }
  .search-input:focus, .sort-select:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .chipbtn {
    font-family: var(--font-body); font-size: 0.78rem; font-weight: 500; color: var(--muted);
    background: var(--surface); border: 1px solid var(--border); border-radius: 999px;
    padding: 5px 12px; cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s;
  }
  .chipbtn:hover { border-color: var(--accent); color: var(--text); }
  .chipbtn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  .link-btn {
    font-family: var(--font-body); font-size: 0.78rem; font-weight: 500; color: var(--accent);
    background: none; border: none; cursor: pointer; padding: 4px 0; text-decoration: underline;
  }

  .deal-list { display: flex; flex-direction: column; gap: 10px; }
  details.deal-row {
    background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--border);
    border-radius: 12px; padding: 0; transition: border-color 0.15s, transform 0.15s;
  }
  details.deal-row[open] { border-left-width: 4px; }
  details.deal-row:hover { transform: translateY(-1px); }
  details.deal-row.state-good { border-left-color: var(--good); }
  details.deal-row.state-watch { border-left-color: var(--watch); }
  .deal-row summary {
    list-style: none; cursor: pointer; padding: 12px 16px;
    display: grid; grid-template-columns: 1fr auto auto auto; align-items: center; gap: 4px 16px;
  }
  .deal-row summary::-webkit-details-marker { display: none; }
  .heart-btn {
    background: none; border: none; cursor: pointer; font-size: 1.2rem; line-height: 1;
    padding: 2px; color: var(--muted);
  }
  .heart-btn.liked { color: var(--heart); }
  .deal-title { font-weight: 600; }
  .deal-sub { font-size: 0.8rem; margin-top: 2px; }
  .price-block { display: flex; flex-direction: column; align-items: flex-end; gap: 1px; }
  .price-was { color: var(--muted); text-decoration: line-through; font-size: 0.8rem; }
  .price-now { font-weight: 700; font-size: 1.15rem; }
  .savings-chip { margin-top: 3px; }
  .caret { color: var(--muted); transition: transform 0.15s; font-size: 0.9rem; }
  details.deal-row[open] .caret { transform: rotate(90deg); }
  .deal-detail { padding: 0 16px 16px; border-top: 1px solid var(--border); margin-top: 2px; }
  .finance-line {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.92rem;
    font-weight: 600; margin-top: 12px;
  }
  .view-btn {
    display: block; text-align: center; margin: 10px 0; padding: 10px 16px;
    background: var(--accent); color: #fff; border-radius: 10px; font-weight: 600;
    font-size: 0.88rem; text-decoration: none;
  }
  .view-btn-disabled { background: var(--surface-2); color: var(--muted); cursor: default; }
  .history-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-top: 10px; }
  .history-table th, .history-table td { text-align: left; padding: 4px 8px 4px 0; color: var(--muted); }
  .history-table td:last-child, .history-table th:last-child { text-align: right; color: var(--text); }
  .sparkline { margin-top: 12px; display: block; }
  .sparkline path.line { fill: none; stroke: var(--accent); stroke-width: 2; }
  .sparkline path.area { fill: var(--accent-soft); stroke: none; }
  .sparkline circle { fill: var(--accent); }
  .sparkline text { font-family: var(--font-mono); font-size: 9px; fill: var(--muted); }

  .sold-panel { margin-top: 10px; }
  .sold-list { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
  .sold-item {
    display: flex; justify-content: space-between; gap: 12px; font-size: 0.82rem;
    padding: 8px 12px; background: var(--surface-2); border-radius: 10px;
  }

  .chip {
    display: inline-block; font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 2px 8px; border-radius: 999px; vertical-align: middle;
  }
  .chip-good { background: var(--good-soft); color: var(--good); }
  .chip-watch { background: var(--watch-soft); color: var(--watch); }
  .chip-over { background: var(--over-soft); color: var(--over); }
  .chip-status { background: var(--surface-2); color: var(--muted); }

  .tips-panel summary {
    cursor: pointer; font-family: var(--font-display); font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; font-size: 1rem; color: var(--muted); list-style: none;
  }
  .tips-panel summary::-webkit-details-marker { display: none; }
  .tips-panel summary::before { content: '\25b8'; display: inline-block; margin-right: 6px; transition: transform 0.15s; }
  .tips-panel[open] summary::before { transform: rotate(90deg); }
  .tips-panel ul { margin: 14px 0 0; padding-left: 20px; font-size: 0.88rem; }
  .tips-panel li { margin-bottom: 8px; }
  .tips-panel li:last-child { margin-bottom: 0; }
  .email-block { margin-top: 12px; }
  .email-block .field-label {
    font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.08em;
    font-size: 0.68rem; color: var(--muted); margin: 0 0 4px;
  }
  .email-subject {
    font-size: 0.82rem; font-weight: 500; background: var(--surface-2); border-radius: 8px;
    padding: 8px 10px; margin-bottom: 8px; user-select: all;
  }
  .email-body {
    width: 100%; min-height: 130px; font-family: var(--font-body); font-size: 0.8rem;
    color: var(--text); background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px; resize: vertical; line-height: 1.5;
  }
  .email-actions { display: flex; gap: 10px; margin-top: 8px; align-items: center; flex-wrap: wrap; }
  .copy-btn {
    font-family: var(--font-body); font-weight: 500; font-size: 0.82rem; color: #fff;
    background: var(--accent); border: none; border-radius: 8px; padding: 7px 14px; cursor: pointer;
  }
  .copy-btn:active { opacity: 0.85; }
  .copy-status { font-size: 0.78rem; color: var(--good); }

  footer.note { color: var(--muted); font-size: 0.78rem; margin-top: 10px; }
  a { color: var(--accent); }
  a:focus-visible, button:focus-visible, .search-input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
  }
</style>
<div class="wrap">
  <p class="eyebrow">92706 &middot; OC / LA / IE &middot; new 4-door hardtop</p>
  <h1>Bronco Watch</h1>
  <p class="meta">Last swept __TODAY__</p>

  <div class="gauge-strip">
    <div class="gauge">
      <p class="eyebrow">Until target buy date</p>
      <div class="gauge-value hero num" data-countup="__DAYS_LEFT__">__DAYS_LEFT__</div>
      <p class="gauge-note">days &middot; __TARGET_LABEL__</p>
    </div>
    <div class="gauge">
      <p class="eyebrow">Trade-in, paid off</p>
      <div class="gauge-value num" data-countup="__TI_TODAY__" data-money="1">__TI_TODAY_FMT__</div>
      <p class="gauge-note">today &middot; baseline __TI_BASELINE_FMT__</p>
    </div>
    <div class="gauge">
      <p class="eyebrow">Projected at target date</p>
      <div class="gauge-value num" data-countup="__TI_PROJECTED__" data-money="1">__TI_PROJECTED_FMT__</div>
      <p class="gauge-note">__TI_DRIFT_SIGN__ __TI_DRIFT_ABS_FMT__ est. drift</p>
    </div>
    <div class="gauge">
      <p class="eyebrow">Cash/finance budget</p>
      <div class="gauge-value num" data-countup="__OOP_CAP_STANDARD__" data-money="1">__OOP_CAP_STANDARD_FMT__</div>
      <p class="gauge-note">up to __OOP_CAP_HIGHER_FMT__ for a higher trim</p>
    </div>
  </div>

  <section>
    <h2 class="sub">Market snapshot</h2>
    <div class="panel">__MARKET_HTML__</div>
  </section>

  <section>
    <h2 class="sub">Upgraded picks &middot; fog lights + 360&deg; camera</h2>
    <div class="deal-list" id="upgradedList"></div>
    <p class="muted small" id="upgradedEmpty" hidden>None found yet &mdash; the daily sweep is watching for Broncos with the Lux Package (360&deg; camera) and fog lights, up to __UPGRADED_ALLOWANCE_FMT__ past your normal budget.</p>
  </section>

  <section>
    <div class="section-head">
      <h2 class="sub">Listings</h2>
      <div class="section-actions">
        <button type="button" class="refresh-btn" id="refreshBtn" title="Ask the tracker to search for new leads">&#8635; Search for new leads</button>
        <span class="count-pill"><span id="dealCount">0</span> shown</span>
      </div>
    </div>
    <p class="refresh-status muted small" id="refreshStatus" hidden></p>

    <div class="controls">
      <div class="controls-row">
        <input type="search" id="dealSearch" class="search-input" placeholder="Search dealer, trim, color&hellip;" aria-label="Search deals">
        <select id="dealSort" class="sort-select" aria-label="Sort deals">
          <option value="price_asc" selected>Price: low to high</option>
          <option value="score">Best deal</option>
          <option value="oop_asc">Cash/finance: low to high</option>
          <option value="price_desc">Price: high to low</option>
          <option value="dom">Days on lot</option>
          <option value="drop">Biggest price drop</option>
        </select>
      </div>
      <div class="controls-row" id="trimChips">
        <button type="button" class="chipbtn" id="favFilterBtn">&#9829; Favorites</button>
        __TRIM_CHIP_BUTTONS__
      </div>
    </div>

    <div class="deal-list" id="dealList"></div>

    <div class="sold-panel">
      <button type="button" class="link-btn" id="soldToggle">Show sold/removed (__SOLD_COUNT__)</button>
      <div class="sold-list" id="soldList" hidden></div>
    </div>

    <footer class="note">Est. cash/finance assumes a __TRADE_IN_VALUE_FMT__ trade-in and CA's __TAX_RATE_FMT__ sales tax (CA taxes the full price - trade-in doesn't reduce it). Green chip = priced below peers or already cut; amber = 21+ days on lot. Tap a listing for its price history and a copyable dealer email.</footer>
  </section>

  <section>
    <details class="tips-panel">
      <summary>Getting the best deal</summary>
      <ul>__TIPS_HTML__</ul>
    </details>
  </section>

  <footer class="note">Trade-in and out-of-pocket figures are planning estimates, not appraisals or dealer quotes.</footer>
</div>

<script type="application/json" id="dealData">__DEALS_JSON__</script>
<script type="application/json" id="soldData">__SOLD_JSON__</script>
<script>
(function () {
  var deals = JSON.parse(document.getElementById('dealData').textContent);
  var sold = JSON.parse(document.getElementById('soldData').textContent);
  var state = { query: '', trims: new Set(), sort: 'price_asc', onlyFavorites: false };
  var dbHandle = null;
  var likedIds = new Set();
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function money(n) {
    if (n == null) return 'n/a';
    return '$' + Math.round(n).toLocaleString('en-US');
  }

  function countUp(el) {
    var target = parseFloat(el.dataset.countup);
    var isMoney = el.dataset.money === '1';
    if (reduceMotion || !isFinite(target)) {
      el.textContent = isMoney ? money(target) : Math.round(target);
      return;
    }
    var start = null, dur = 700;
    function tick(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      var val = target * eased;
      el.textContent = isMoney ? money(val) : Math.round(val);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  document.querySelectorAll('[data-countup]').forEach(countUp);

  function sparkline(history) {
    if (!history || history.length < 2) return '';
    var w = 260, h = 56, pad = 8;
    var prices = history.map(function (p) { return p.price; });
    var min = Math.min.apply(null, prices), max = Math.max.apply(null, prices);
    var span = (max - min) || 1;
    var pts = history.map(function (p, i) {
      var x = pad + (i / (history.length - 1)) * (w - pad * 2);
      var y = h - pad - ((p.price - min) / span) * (h - pad * 2);
      return [x, y];
    });
    var line = pts.map(function (p, i) { return (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join(' ');
    var area = line + ' L' + pts[pts.length - 1][0].toFixed(1) + ' ' + (h - pad) + ' L' + pts[0][0].toFixed(1) + ' ' + (h - pad) + ' Z';
    var dots = pts.map(function (p, i) {
      var isEnd = i === 0 || i === pts.length - 1;
      return isEnd ? '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="2.5"></circle>' : '';
    }).join('');
    return '<svg class="sparkline" viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="' + h + '" role="img" aria-label="Price history">' +
      '<path class="area" d="' + area + '"></path>' +
      '<path class="line" d="' + line + '"></path>' + dots +
      '<text x="' + pts[0][0] + '" y="' + (h - 1) + '">' + esc(money(prices[0])) + '</text>' +
      '<text x="' + pts[pts.length - 1][0] + '" y="' + (h - 1) + '" text-anchor="end">' + esc(money(prices[prices.length - 1])) + '</text>' +
      '</svg>';
  }

  function historyTable(history) {
    if (!history || !history.length) return '';
    var rows = history.map(function (p) {
      return '<tr><td>' + esc(p.date) + '</td><td>' + esc(money(p.price)) + '</td></tr>';
    }).join('');
    return '<table class="history-table"><thead><tr><th>Date</th><th>Price</th></tr></thead><tbody>' + rows + '</tbody></table>';
  }

  function dealState(d) {
    if (d.is_stale) return 'watch';
    if (d.pct_below_peer_avg >= 5 || d.price_drop > 0) return 'good';
    return 'neutral';
  }
  function stateChip(state) {
    if (state === 'good') return '<span class="chip chip-good">deal</span>';
    if (state === 'watch') return '<span class="chip chip-watch">watch</span>';
    return '';
  }
  function budgetChip(b) {
    return b.within_budget
      ? '<span class="chip chip-good">in budget</span>'
      : '<span class="chip chip-over">+' + esc(money(b.over_by)) + '</span>';
  }

  function renderDeal(d) {
    var s = dealState(d);
    var b = d.budget || {};
    var link = d.url
      ? '<a class="view-btn" href="' + esc(d.url) + '" target="_blank" rel="noopener">View listing &rarr;</a>'
      : '<span class="view-btn view-btn-disabled">No link saved</span>';
    var emailId = 'email-body-' + esc(d.id);
    var emailBlock = (d.email && d.email.body)
      ? '<div class="email-block">' +
          '<p class="field-label">Email template &mdash; copy and paste into a new message</p>' +
          '<div class="email-subject">' + esc(d.email.subject) + '</div>' +
          '<textarea class="email-body" id="' + emailId + '" readonly>' + esc(d.email.body) + '</textarea>' +
          '<div class="email-actions">' +
            '<button type="button" class="copy-btn" data-copy-target="' + emailId + '">Copy email</button>' +
            '<span class="copy-status" data-status-for="' + emailId + '" hidden>Copied</span>' +
          '</div>' +
        '</div>'
      : '';
    var liked = likedIds.has(d.id);
    var heartBtn = '<button type="button" class="heart-btn' + (liked ? ' liked' : '') + '" data-heart-id="' +
      esc(d.id) + '" aria-label="' + (liked ? 'Remove from favorites' : 'Add to favorites') + '">' +
      (liked ? '&#9829;' : '&#9825;') + '</button>';

    // Price block: MSRP strikethrough (if known) or peer-average strikethrough,
    // current price bold, and a savings/drop badge - mirrors how CarGurus etc.
    // show "was/now" pricing.
    var wasPrice = null, savingsLabel = '';
    if (d.msrp && d.msrp > d.price) {
      wasPrice = d.msrp;
      savingsLabel = 'below MSRP';
    } else if (d.price_drop > 0) {
      wasPrice = d.price + d.price_drop;
      savingsLabel = 'price drop';
    }
    var savingsAmt = wasPrice ? (wasPrice - d.price) : 0;
    var priceBlock = '<div class="price-block">' +
      (wasPrice ? '<span class="price-was num">' + esc(money(wasPrice)) + '</span>' : '') +
      '<span class="price-now num">' + esc(money(d.price)) + '</span>' +
      '</div>' +
      (savingsAmt > 0
        ? '<span class="chip chip-good savings-chip">&minus;' + esc(money(savingsAmt)) + ' ' + savingsLabel + '</span>'
        : '');

    return '<details class="deal-row state-' + s + '">' +
      '<summary>' +
        '<div>' +
          '<div class="deal-title">' + esc(d.trim) + ' 4-Door 4WD ' + stateChip(s) +
            (b.upgraded ? ' <span class="chip chip-status">upgraded</span>' : '') + '</div>' +
          '<div class="deal-sub muted">' + esc(d.color_exterior || 'color n/a') + ' &middot; ' + esc(d.location || d.dealer) +
            ' &mdash; ' + esc(d.days_on_market) + ' days on lot</div>' +
        '</div>' +
        priceBlock +
        heartBtn +
        '<span class="caret">&#9656;</span>' +
      '</summary>' +
      '<div class="deal-detail">' +
        '<div class="finance-line">' +
          '<span class="num">' + esc(money(b.est_monthly_payment)) + '/mo est.</span>' +
          '<span class="muted">&middot;</span>' +
          '<span class="num">' + esc(money(b.out_of_pocket)) + ' cash/finance</span>' +
          budgetChip(b) +
        '</div>' +
        '<p class="muted small">' + esc(d.dealer) + ' &middot; ' + esc(d.pct_below_peer_avg) + '% vs peer avg' + '</p>' +
        link +
        sparkline(d.price_history) +
        historyTable(d.price_history) +
        emailBlock +
      '</div>' +
    '</details>';
  }

  function applyFilters() {
    var q = state.query.toLowerCase();
    var rows = deals.filter(function (d) {
      if (state.onlyFavorites && !likedIds.has(d.id)) return false;
      if (state.trims.size && !state.trims.has(d.trim)) return false;
      if (q) {
        var hay = [d.trim, d.color_exterior, d.dealer, d.location].join(' ').toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    var sorters = {
      score: function (a, b) { return b.score - a.score; },
      oop_asc: function (a, b) { return (a.budget.out_of_pocket || 0) - (b.budget.out_of_pocket || 0); },
      price_asc: function (a, b) { return (a.price || 0) - (b.price || 0); },
      price_desc: function (a, b) { return (b.price || 0) - (a.price || 0); },
      dom: function (a, b) { return b.days_on_market - a.days_on_market; },
      drop: function (a, b) { return b.price_drop - a.price_drop; }
    };
    rows.sort(sorters[state.sort] || sorters.score);
    return rows;
  }

  function render() {
    var rows = applyFilters();
    document.getElementById('dealCount').textContent = rows.length;
    document.getElementById('dealList').innerHTML = rows.length
      ? rows.map(renderDeal).join('')
      : "<p class='muted'>No listings match these filters.</p>";
  }

  function renderUpgraded() {
    var rows = deals.filter(function (d) { return d.budget && d.budget.upgraded; });
    document.getElementById('upgradedList').innerHTML = rows.map(renderDeal).join('');
    document.getElementById('upgradedEmpty').hidden = rows.length > 0;
  }

  function toggleHeart(id) {
    if (!dbHandle) return;
    var wasLiked = likedIds.has(id);
    if (wasLiked) likedIds.delete(id); else likedIds.add(id);
    render();
    renderUpgraded();
    var ref = dbHandle.doc('hearts/' + id);
    var write = wasLiked ? ref.delete() : ref.set({ liked: true });
    write.catch(function () {
      if (wasLiked) likedIds.add(id); else likedIds.delete(id);
      render();
      renderUpgraded();
    });
  }

  function updateRefreshUI(data) {
    var btn = document.getElementById('refreshBtn');
    var status = document.getElementById('refreshStatus');
    if (!data) { status.hidden = true; btn.disabled = false; return; }
    status.hidden = false;
    if (data.fulfilled) {
      status.textContent = 'Last refreshed ' + new Date(data.fulfilled_at).toLocaleString();
      btn.disabled = false;
    } else {
      status.textContent = 'Refresh requested — checked within the hour.';
      btn.disabled = true;
    }
  }

  function useDb() {
    if (window.claude && typeof window.claude.use === 'function') {
      return window.claude.use('db').catch(function () { return null; });
    }
    return Promise.resolve(null);
  }

  useDb().then(function (db) {
    dbHandle = db;
    if (!db) return;
    db.collection('hearts').get().then(function (snap) {
      snap.docs.forEach(function (doc) {
        var data = doc.data();
        if (data && data.liked) likedIds.add(doc.id);
      });
      render();
      renderUpgraded();
    }).catch(function () {});
    db.doc('requests/manual-refresh').get().then(function (snap) {
      updateRefreshUI(snap.exists ? snap.data() : null);
    }).catch(function () {});
  });

  document.getElementById('refreshBtn').addEventListener('click', function () {
    var status = document.getElementById('refreshStatus');
    if (!dbHandle) {
      status.hidden = false;
      status.textContent = 'Not available in this preview — ask Claude in chat to run a sweep instead.';
      return;
    }
    var now = new Date().toISOString();
    this.disabled = true;
    dbHandle.doc('requests/manual-refresh').set({ requested_at: now, fulfilled: false }).then(function () {
      updateRefreshUI({ requested_at: now, fulfilled: false });
    }).catch(function () {
      status.hidden = false;
      status.textContent = 'Could not send the request — try again in a moment.';
    });
  });

  document.getElementById('dealSearch').addEventListener('input', function (e) {
    state.query = e.target.value;
    render();
  });
  document.getElementById('dealSort').addEventListener('change', function (e) {
    state.sort = e.target.value;
    render();
  });
  document.getElementById('trimChips').addEventListener('click', function (e) {
    var favBtn = e.target.closest('#favFilterBtn');
    if (favBtn) {
      state.onlyFavorites = !state.onlyFavorites;
      favBtn.classList.toggle('active', state.onlyFavorites);
      render();
      return;
    }
    var btn = e.target.closest('.chipbtn[data-trim]');
    if (!btn) return;
    var trim = btn.dataset.trim;
    if (state.trims.has(trim)) { state.trims.delete(trim); btn.classList.remove('active'); }
    else { state.trims.add(trim); btn.classList.add('active'); }
    render();
  });

  var soldToggle = document.getElementById('soldToggle');
  var soldList = document.getElementById('soldList');
  soldToggle.addEventListener('click', function () {
    var showing = !soldList.hidden;
    if (showing) { soldList.hidden = true; return; }
    if (!soldList.dataset.rendered) {
      soldList.innerHTML = sold.length ? sold.map(function (d) {
        return '<div class="sold-item"><span>' + esc(d.trim) + ' &middot; ' + esc(d.color_exterior) + ' &mdash; ' + esc(d.dealer) +
          '</span><span class="chip chip-status">' + esc(d.status) + ' &middot; ' + esc(d.days_on_market) + 'd</span></div>';
      }).join('') : "<p class='muted small'>None yet.</p>";
      soldList.dataset.rendered = '1';
    }
    soldList.hidden = false;
  });

  document.addEventListener('click', function (e) {
    var heartBtn = e.target.closest('.heart-btn');
    if (heartBtn) {
      e.preventDefault();
      e.stopPropagation();
      toggleHeart(heartBtn.dataset.heartId);
      return;
    }
    var btn = e.target.closest('.copy-btn');
    if (!btn) return;
    var textarea = document.getElementById(btn.dataset.copyTarget);
    if (!textarea) return;
    var status = document.querySelector('[data-status-for="' + btn.dataset.copyTarget + '"]');
    function showCopied() {
      if (!status) return;
      status.hidden = false;
      clearTimeout(status._hideTimer);
      status._hideTimer = setTimeout(function () { status.hidden = true; }, 2000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(textarea.value).then(showCopied).catch(function () {
        textarea.focus();
        textarea.select();
        try { document.execCommand('copy'); showCopied(); } catch (err) {}
      });
    } else {
      textarea.focus();
      textarea.select();
      try { document.execCommand('copy'); showCopied(); } catch (err) {}
    }
  });

  render();
  renderUpgraded();
})();
</script>
"""

    replacements = {
        "__TODAY__": data["today"],
        "__DAYS_LEFT__": str(data["days_left"]),
        "__TARGET_LABEL__": config.TARGET_BUY_DATE.strftime("%b %-d, %Y"),
        "__TI_TODAY__": str(ti["as_of_today"]),
        "__TI_TODAY_FMT__": _fmt_money(ti["as_of_today"]),
        "__TI_BASELINE_FMT__": _fmt_money(ti["baseline_value"]),
        "__TI_PROJECTED__": str(ti["projected_at_target"]),
        "__TI_PROJECTED_FMT__": _fmt_money(ti["projected_at_target"]),
        "__TI_DRIFT_SIGN__": "&minus;" if ti["estimated_drift"] < 0 else "+",
        "__TI_DRIFT_ABS_FMT__": _fmt_money(abs(ti["estimated_drift"])),
        "__MARKET_HTML__": market_html,
        "__UPGRADED_ALLOWANCE_FMT__": _fmt_money(config.UPGRADED_OOP_ALLOWANCE),
        "__TRIM_CHIP_BUTTONS__": trim_chip_buttons,
        "__SOLD_COUNT__": str(len(sold)),
        "__DEALS_JSON__": deals_json,
        "__SOLD_JSON__": sold_json,
        "__OOP_CAP_STANDARD__": str(config.OOP_CAP_STANDARD),
        "__OOP_CAP_STANDARD_FMT__": _fmt_money(config.OOP_CAP_STANDARD),
        "__OOP_CAP_HIGHER_FMT__": _fmt_money(config.OOP_CAP_HIGHER_TRIM),
        "__TRADE_IN_VALUE_FMT__": _fmt_money(data["trade_in_value"]),
        "__TAX_RATE_FMT__": f"{config.SALES_TAX_RATE:.2%}",
        "__TIPS_HTML__": "".join(f"<li>{_e(tip)}</li>" for tip in budget.NEGOTIATION_TIPS),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template


def write_report() -> str:
    text = build_report()
    with open(config.REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    with open(config.REPORT_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(build_html_report())
    with open(config.REPORT_ARTIFACT_FILE, "w", encoding="utf-8") as f:
        f.write(build_artifact_html())
    return text
