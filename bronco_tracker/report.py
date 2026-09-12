"""Generate the human-readable report from tracked data (markdown + HTML)."""
from __future__ import annotations

import html as html_escape
from datetime import date
from typing import Any

from . import config, deals, storage, trade_in


def _fmt_money(n) -> str:
    return f"${n:,.0f}" if n is not None else "n/a"


def _gather() -> dict[str, Any]:
    listings = storage.load_listings()
    return {
        "ranked": deals.rank_deals(listings),
        "sold": deals.inactive_summaries(listings),
        "trends": deals.trend_summary(listings),
        "ti": trade_in.projection_to_target(storage.load_trade_in()),
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


def _e(value: Any) -> str:
    return html_escape.escape(str(value)) if value is not None else "?"


def build_html_report() -> str:
    data = _gather()
    ranked, trends, ti = data["ranked"], data["trends"], data["ti"]

    if trends["count"] == 0:
        market_html = "<p class='muted'>No active listings tracked yet.</p>"
    else:
        trim_rows = "".join(
            f"<li>{_e(trim)}: <strong>{_fmt_money(avg)}</strong></li>"
            for trim, avg in sorted(trends["avg_price_by_trim"].items(), key=lambda kv: kv[1])
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
        <p><strong>Average price by trim:</strong></p>
        <ul>{trim_rows}</ul>
        """

    if not ranked:
        deals_html = "<p class='muted'>Nothing tracked yet. Add listings as you find them.</p>"
    else:
        rows = []
        for r in ranked:
            stale = " <span class='badge'>stale</span>" if r["is_stale"] else ""
            drop = f"-{_fmt_money(r['price_drop'])}" if r["price_drop"] > 0 else "&mdash;"
            url = _e(r.get("url", "")) if r.get("url") else ""
            link = f"<a href='{url}' target='_blank' rel='noopener'>view</a>" if url else "&mdash;"
            rows.append(f"""
              <tr>
                <td class="score">{r['score']}</td>
                <td>{_e(r.get('trim'))}</td>
                <td>{_e(r.get('color_exterior'))}</td>
                <td>{_fmt_money(r.get('price'))}</td>
                <td>{r['pct_below_peer_avg']}%</td>
                <td>{r['days_on_market']}{stale}</td>
                <td>{drop}</td>
                <td>{_e(r.get('dealer'))}</td>
                <td>{link}</td>
              </tr>""")
        deals_html = f"""
        <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Score</th><th>Trim</th><th>Color</th><th>Price</th><th>vs peer avg</th>
            <th>Days on market</th><th>Price drop</th><th>Dealer</th><th></th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        </div>
        """

    drift_sign = "-" if ti["estimated_drift"] < 0 else "+"

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

  <div class="card">
    <h2>Ranked deals (best first)</h2>
    {deals_html}
    <footer>Score blends price-vs-peer-average, days on market, and observed price drops. "stale" = 21+ days on market, typically more negotiable.</footer>
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
            f"<div class='trim-row'><span>{_e(trim)}</span><span class='num'>{_fmt_money(avg)}</span></div>"
            for trim, avg in sorted(trends["avg_price_by_trim"].items(), key=lambda kv: kv[1])
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
        <h3 class="sub">Average price by trim</h3>
        <div class="trim-list">{trim_chips}</div>
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
    --bg: #eef0e6; --surface: #ffffff; --surface-2: #f6f7f0;
    --text: #20241c; --muted: #6d7161; --border: #dadcc9;
    --accent: #cc531a; --accent-soft: #fbe6d6; --accent-ink: #7a3410;
    --good: #2f7d4f; --good-soft: #e2f2e6;
    --watch: #a3721b; --watch-soft: #f7ecd2;
    --font-display: "Big Shoulders Display", "Arial Narrow", sans-serif;
    --font-body: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #14170f; --surface: #1c2016; --surface-2: #20241a;
      --text: #edf0e4; --muted: #98a086; --border: #343925;
      --accent: #ff8a4a; --accent-soft: #3c2415; --accent-ink: #ffcaa3;
      --good: #63c088; --good-soft: #1e3324;
      --watch: #e3b552; --watch-soft: #3a2f14;
    }
  }
  :root[data-theme="dark"] {
    --bg: #14170f; --surface: #1c2016; --surface-2: #20241a;
    --text: #edf0e4; --muted: #98a086; --border: #343925;
    --accent: #ff8a4a; --accent-soft: #3c2415; --accent-ink: #ffcaa3;
    --good: #63c088; --good-soft: #1e3324;
    --watch: #e3b552; --watch-soft: #3a2f14;
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
  .count-pill {
    font-family: var(--font-mono); font-size: 0.72rem; color: var(--muted);
    background: var(--surface-2); border-radius: 999px; padding: 2px 10px;
  }

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
    display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 4px 16px;
  }
  .deal-row summary::-webkit-details-marker { display: none; }
  .deal-title { font-weight: 600; }
  .deal-sub { font-size: 0.8rem; margin-top: 2px; }
  .deal-figures { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
  .deal-price { font-weight: 600; font-size: 1.05rem; }
  .deal-vs { color: var(--muted); }
  .delta.down { color: var(--good); font-family: var(--font-mono); font-size: 0.82rem; }
  .caret { color: var(--muted); transition: transform 0.15s; font-size: 0.9rem; }
  details.deal-row[open] .caret { transform: rotate(90deg); }
  .deal-detail { padding: 0 16px 16px; border-top: 1px solid var(--border); margin-top: 2px; }
  .deal-detail .deal-link { margin-top: 10px; display: block; }
  .deal-detail .deal-link a { color: var(--accent); font-size: 0.82rem; font-weight: 500; }
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
  .chip-status { background: var(--surface-2); color: var(--muted); }

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
  </div>

  <section>
    <h2 class="sub">Market snapshot</h2>
    <div class="panel">__MARKET_HTML__</div>
  </section>

  <section>
    <div class="section-head">
      <h2 class="sub">Ranked deals</h2>
      <span class="count-pill"><span id="dealCount">0</span> shown</span>
    </div>

    <div class="controls">
      <div class="controls-row">
        <input type="search" id="dealSearch" class="search-input" placeholder="Search dealer, trim, color&hellip;" aria-label="Search deals">
        <select id="dealSort" class="sort-select" aria-label="Sort deals">
          <option value="score">Best deal</option>
          <option value="price_asc">Price: low to high</option>
          <option value="price_desc">Price: high to low</option>
          <option value="dom">Days on lot</option>
          <option value="drop">Biggest price drop</option>
        </select>
      </div>
      <div class="controls-row" id="trimChips">__TRIM_CHIP_BUTTONS__</div>
    </div>

    <div class="deal-list" id="dealList"></div>

    <div class="sold-panel">
      <button type="button" class="link-btn" id="soldToggle">Show sold/removed (__SOLD_COUNT__)</button>
      <div class="sold-list" id="soldList" hidden></div>
    </div>

    <footer class="note">Green = priced below peers or already cut. Amber = 21+ days on lot, worth a call. Tap a listing to see its price history. Ranked by a blend of price-vs-peers, days on lot, and observed price cuts.</footer>
  </section>

  <footer class="note">Trade-in figures are a planning estimate (compounding monthly depreciation), not an appraisal.</footer>
</div>

<script type="application/json" id="dealData">__DEALS_JSON__</script>
<script type="application/json" id="soldData">__SOLD_JSON__</script>
<script>
(function () {
  var deals = JSON.parse(document.getElementById('dealData').textContent);
  var sold = JSON.parse(document.getElementById('soldData').textContent);
  var state = { query: '', trims: new Set(), sort: 'score' };
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

  function renderDeal(d) {
    var s = dealState(d);
    var drop = d.price_drop > 0
      ? '<span class="delta down">&minus;' + esc(money(d.price_drop)) + '</span>'
      : '<span class="muted small">&mdash;</span>';
    var link = d.url ? '<div class="deal-link"><a href="' + esc(d.url) + '" target="_blank" rel="noopener">listing &rarr;</a></div>' : '';
    return '<details class="deal-row state-' + s + '">' +
      '<summary>' +
        '<div>' +
          '<div class="deal-title">' + esc(d.trim) + ' &middot; ' + esc(d.color_exterior) + ' ' + stateChip(s) + '</div>' +
          '<div class="deal-sub muted">' + esc(d.dealer) + ' &mdash; ' + esc(d.days_on_market) + ' days on lot</div>' +
        '</div>' +
        '<div class="deal-figures">' +
          '<span class="deal-price num">' + esc(money(d.price)) + '</span>' +
          '<span class="deal-vs num small">' + esc(d.pct_below_peer_avg) + '% vs peers</span>' +
          drop +
        '</div>' +
        '<span class="caret">&#9656;</span>' +
      '</summary>' +
      '<div class="deal-detail">' +
        sparkline(d.price_history) +
        historyTable(d.price_history) +
        link +
      '</div>' +
    '</details>';
  }

  function applyFilters() {
    var q = state.query.toLowerCase();
    var rows = deals.filter(function (d) {
      if (state.trims.size && !state.trims.has(d.trim)) return false;
      if (q) {
        var hay = [d.trim, d.color_exterior, d.dealer, d.location].join(' ').toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    var sorters = {
      score: function (a, b) { return b.score - a.score; },
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

  document.getElementById('dealSearch').addEventListener('input', function (e) {
    state.query = e.target.value;
    render();
  });
  document.getElementById('dealSort').addEventListener('change', function (e) {
    state.sort = e.target.value;
    render();
  });
  document.getElementById('trimChips').addEventListener('click', function (e) {
    var btn = e.target.closest('.chipbtn');
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

  render();
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
        "__TRIM_CHIP_BUTTONS__": trim_chip_buttons,
        "__SOLD_COUNT__": str(len(sold)),
        "__DEALS_JSON__": deals_json,
        "__SOLD_JSON__": sold_json,
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
