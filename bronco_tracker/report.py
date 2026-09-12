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


def _deal_state(r: dict[str, Any]) -> tuple[str, str]:
    """Classify a ranked listing for the stripe/chip treatment: (state, label)."""
    if r["is_stale"]:
        return "watch", "watch"
    if r["pct_below_peer_avg"] >= 5 or r["price_drop"] > 0:
        return "good", "deal"
    return "neutral", ""


def build_artifact_html() -> str:
    """Build the artifact-ready fragment: <title> + <style> + body content,
    no <!doctype>/<html>/<head>/<body> - the Artifact host wraps those.
    """
    data = _gather()
    ranked, trends, ti = data["ranked"], data["trends"], data["ti"]

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
        <p class="muted small">{trends['sold_or_removed_count']} sold/removed since tracking began.</p>
        <h3 class="sub">Average price by trim</h3>
        <div class="trim-list">{trim_chips}</div>
        """

    if not ranked:
        deals_html = "<p class='muted'>Nothing tracked yet &mdash; listings land here as the daily sweep finds them.</p>"
    else:
        rows = []
        for r in ranked:
            state, label = _deal_state(r)
            chip = f"<span class='chip chip-{state}'>{label}</span>" if label else ""
            drop = f"<span class='delta down'>&minus;{_fmt_money(r['price_drop'])}</span>" if r["price_drop"] > 0 else "<span class='muted'>&mdash;</span>"
            url = _e(r.get("url", "")) if r.get("url") else ""
            link = f"<a href='{url}' target='_blank' rel='noopener'>listing &rarr;</a>" if url else ""
            rows.append(f"""
            <div class="deal-row state-{state}">
              <div class="deal-main">
                <div class="deal-title">{_e(r.get('trim'))} &middot; {_e(r.get('color_exterior'))} {chip}</div>
                <div class="deal-sub muted">{_e(r.get('dealer'))} &mdash; {r['days_on_market']} days on lot</div>
              </div>
              <div class="deal-figures">
                <span class="deal-price num">{_fmt_money(r.get('price'))}</span>
                <span class="deal-vs num small">{r['pct_below_peer_avg']}% vs peers</span>
                {drop}
              </div>
              <div class="deal-link">{link}</div>
            </div>""")
        deals_html = f"<div class='deal-list'>{''.join(rows)}</div>"

    drift_sign = "&minus;" if ti["estimated_drift"] < 0 else "+"

    return f"""<title>Bronco Watch</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap">
<style>
  :root {{
    --bg: #eef0e6; --surface: #ffffff; --surface-2: #f6f7f0;
    --text: #20241c; --muted: #6d7161; --border: #dadcc9;
    --accent: #cc531a; --accent-soft: #fbe6d6; --accent-ink: #7a3410;
    --good: #2f7d4f; --good-soft: #e2f2e6;
    --watch: #a3721b; --watch-soft: #f7ecd2;
    --font-display: "Big Shoulders Display", "Arial Narrow", sans-serif;
    --font-body: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #14170f; --surface: #1c2016; --surface-2: #20241a;
      --text: #edf0e4; --muted: #98a086; --border: #343925;
      --accent: #ff8a4a; --accent-soft: #3c2415; --accent-ink: #ffcaa3;
      --good: #63c088; --good-soft: #1e3324;
      --watch: #e3b552; --watch-soft: #3a2f14;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #14170f; --surface: #1c2016; --surface-2: #20241a;
    --text: #edf0e4; --muted: #98a086; --border: #343925;
    --accent: #ff8a4a; --accent-soft: #3c2415; --accent-ink: #ffcaa3;
    --good: #63c088; --good-soft: #1e3324;
    --watch: #e3b552; --watch-soft: #3a2f14;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--font-body); line-height: 1.5;
  }}
  .wrap {{ max-width: 780px; margin: 0 auto; padding: 28px 18px 56px; }}
  .num {{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; }}
  .muted {{ color: var(--muted); }}
  .small {{ font-size: 0.8rem; }}
  .eyebrow {{
    font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.12em;
    font-size: 0.72rem; color: var(--muted); margin: 0 0 6px;
  }}
  h1 {{
    font-family: var(--font-display); font-weight: 800; font-size: clamp(2.1rem, 8vw, 2.8rem);
    letter-spacing: 0.01em; margin: 0 0 4px; text-wrap: balance;
  }}
  h2.sub, h3.sub {{
    font-family: var(--font-display); font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; font-size: 1rem; color: var(--muted); margin: 0 0 12px;
  }}
  .meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 22px; }}

  .gauge-strip {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 14px; margin-bottom: 22px;
  }}
  .gauge {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 16px 18px;
  }}
  .gauge .eyebrow {{ margin-bottom: 8px; }}
  .gauge-value {{
    font-family: var(--font-display); font-weight: 800; font-size: 2.1rem;
    color: var(--accent-ink, var(--text)); line-height: 1;
  }}
  .gauge-value.hero {{ color: var(--accent); }}
  .gauge-note {{ margin-top: 6px; font-size: 0.78rem; color: var(--muted); }}

  section {{ margin-bottom: 24px; }}
  .panel {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 18px 20px;
  }}

  .tile-grid {{ display: flex; flex-wrap: wrap; gap: 18px; margin-bottom: 14px; }}
  .tile {{ display: flex; flex-direction: column; min-width: 120px; }}
  .tile-value {{ font-size: 1.35rem; font-weight: 600; }}
  .tile-label {{ color: var(--muted); font-size: 0.76rem; margin-top: 2px; }}

  .range-line {{ display: flex; align-items: center; gap: 10px; font-size: 0.85rem; margin: 10px 0 4px; }}
  .range-track {{ flex: 1; height: 4px; background: var(--surface-2); border-radius: 2px; overflow: hidden; }}
  .range-fill {{ display: block; height: 100%; width: 100%; background: var(--accent); opacity: 0.55; }}

  .trim-list {{ border-top: 1px solid var(--border); }}
  .trim-row {{
    display: flex; justify-content: space-between; padding: 8px 0;
    border-bottom: 1px solid var(--border); font-size: 0.88rem;
  }}

  .deal-list {{ display: flex; flex-direction: column; gap: 10px; }}
  .deal-row {{
    display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 4px 16px;
    background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--border);
    border-radius: 12px; padding: 12px 16px;
  }}
  .deal-row.state-good {{ border-left-color: var(--good); }}
  .deal-row.state-watch {{ border-left-color: var(--watch); }}
  .deal-title {{ font-weight: 600; }}
  .deal-sub {{ font-size: 0.8rem; margin-top: 2px; }}
  .deal-figures {{ display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }}
  .deal-price {{ font-weight: 600; font-size: 1.05rem; }}
  .deal-vs {{ color: var(--muted); }}
  .delta.down {{ color: var(--good); font-family: var(--font-mono); font-size: 0.82rem; }}
  .deal-link {{ grid-column: 1 / -1; }}
  .deal-link a {{ color: var(--accent); text-decoration: none; font-size: 0.82rem; font-weight: 500; }}
  .deal-link a:hover {{ text-decoration: underline; }}

  .chip {{
    display: inline-block; font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 2px 8px; border-radius: 999px; vertical-align: middle;
  }}
  .chip-good {{ background: var(--good-soft); color: var(--good); }}
  .chip-watch {{ background: var(--watch-soft); color: var(--watch); }}

  footer.note {{ color: var(--muted); font-size: 0.78rem; margin-top: 10px; }}
  a {{ color: var(--accent); }}
  a:focus-visible, button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
</style>
<div class="wrap">
  <p class="eyebrow">92706 &middot; OC / LA / IE &middot; new 4-door hardtop</p>
  <h1>Bronco Watch</h1>
  <p class="meta">Last swept {data['today']}</p>

  <div class="gauge-strip">
    <div class="gauge">
      <p class="eyebrow">Until target buy date</p>
      <div class="gauge-value hero num">{data['days_left']}</div>
      <p class="gauge-note">days &middot; {config.TARGET_BUY_DATE.strftime('%b %-d, %Y')}</p>
    </div>
    <div class="gauge">
      <p class="eyebrow">Trade-in, paid off</p>
      <div class="gauge-value num">{_fmt_money(ti['as_of_today'])}</div>
      <p class="gauge-note">today &middot; baseline {_fmt_money(ti['baseline_value'])}</p>
    </div>
    <div class="gauge">
      <p class="eyebrow">Projected at target date</p>
      <div class="gauge-value num">{_fmt_money(ti['projected_at_target'])}</div>
      <p class="gauge-note">{drift_sign}{_fmt_money(abs(ti['estimated_drift']))} est. drift</p>
    </div>
  </div>

  <section>
    <h2 class="sub">Market snapshot</h2>
    <div class="panel">{market_html}</div>
  </section>

  <section>
    <h2 class="sub">Ranked deals</h2>
    {deals_html}
    <footer class="note">Green = priced below peers or already cut. Amber = 21+ days on lot, worth a call. Ranked by a blend of price-vs-peers, days on lot, and observed price cuts.</footer>
  </section>

  <footer class="note">Trade-in figures are a planning estimate (compounding monthly depreciation), not an appraisal.</footer>
</div>
"""


def write_report() -> str:
    text = build_report()
    with open(config.REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    with open(config.REPORT_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(build_html_report())
    with open(config.REPORT_ARTIFACT_FILE, "w", encoding="utf-8") as f:
        f.write(build_artifact_html())
    return text
