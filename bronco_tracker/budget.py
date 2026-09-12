"""Out-of-pocket cost estimate and the dealer outreach template.

Two things buyers get wrong on a trade-in deal: they compare sticker
prices instead of what they'll actually pay, and they negotiate price
and trade-in together where a dealer can hide markup in either number.
This module estimates the real cash/finance number (CA taxes the full
price - no trade-in credit) and gives a ready-to-send message that keeps
the two numbers separate.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from . import config


def is_upgraded(record: dict[str, Any]) -> bool:
    """Fog lights + 360-degree camera - the buyer's separate "upgraded" tier."""
    return bool(record.get("has_fog_lights")) and bool(record.get("has_360_camera"))


def monthly_payment(principal: float, apr: float = config.FINANCE_APR, term_months: int = config.FINANCE_TERM_MONTHS) -> int:
    """Standard loan amortization payment. Planning estimate only."""
    principal = max(principal, 0)
    rate = apr / 12
    if rate == 0:
        return round(principal / term_months)
    factor = (1 + rate) ** term_months
    return round(principal * rate * factor / (factor - 1))


def estimate_out_of_pocket(price: int | None, trim: str | None, trade_in_value: float, upgraded: bool = False) -> dict[str, Any]:
    price = price or 0
    tax = round(price * config.SALES_TAX_RATE)
    fees = config.DOC_FEE + config.EST_REG_TITLE_FEES
    est_otd = price + tax + fees
    out_of_pocket = round(est_otd - trade_in_value)
    cap = config.oop_cap_for_trim(trim, upgraded=upgraded)

    return {
        "price": price,
        "estimated_tax": tax,
        "estimated_fees": fees,
        "estimated_otd": round(est_otd),
        "trade_in_applied": round(trade_in_value),
        "out_of_pocket": out_of_pocket,
        "out_of_pocket_cap": cap,
        "within_budget": out_of_pocket <= cap,
        "over_by": max(out_of_pocket - cap, 0),
        "upgraded": upgraded,
        "est_monthly_payment": monthly_payment(out_of_pocket),
    }


def email_template(record: dict[str, Any], trade_in_value: float) -> dict[str, str]:
    """A copy/paste-ready message asking a dealer for their best out-the-door
    price. Deliberately doesn't mention the trade-in dollar amount - ask for
    the vehicle's OTD price and the trade appraisal as two separate numbers
    so neither can be used to obscure markup in the other.
    """
    trim = record.get("trim", "Bronco")
    color = record.get("color_exterior", "")
    stock = record.get("stock_number", "")
    dealer = record.get("dealer", "")

    subject = f"Best OTD price - {trim} {color} #{stock}".strip()
    body = (
        f"Hi,\n\n"
        f"I'm interested in the {trim}{' ' + color if color else ''} "
        f"(stock #{stock}) listed at {dealer}.\n\n"
        f"I'm a ready buyer - cash or financing, no add-ons - and I'm comparing offers "
        f"from a few dealers this week. Could you send me your best out-the-door price "
        f"(total with tax, doc fee, and DMV, before any trade-in)?\n\n"
        f"Separately, I have a paid-off trade-in (roughly ${round(trade_in_value):,}) "
        f"I'd like appraised - please quote that as its own number rather than folded "
        f"into the vehicle price.\n\n"
        f"Thanks,\n"
    )
    return {
        "subject": subject,
        "body": body,
        "mailto": f"mailto:?subject={quote(subject)}&body={quote(body)}",
    }


NEGOTIATION_TIPS = [
    "Email 3-4 dealers the identical message with the stock number and ask for their best out-the-door (OTD) price - total with tax, doc fee, and DMV, before any trade-in.",
    "Get the vehicle price and the trade-in appraisal as two separate numbers. A dealer can hide markup in either one if they're combined into a single 'you'll pay X' figure.",
    "Never negotiate off MSRP or a monthly payment - only the total OTD number. A low monthly payment can hide a longer loan term or a bad trade value.",
    "Reply to the lowest OTD quote you get and ask the others if they'll beat it - dealers will often move on a real competing number in writing.",
    "Get the OTD quote in an email or text before you visit, so there's a paper trail if the in-person number changes.",
    "End of month/quarter, dealers are more motivated to hit sales quotas - a stale listing (21+ days) is extra leverage on top of that.",
]
