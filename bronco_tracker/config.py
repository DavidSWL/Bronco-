"""Search criteria and constants for the Bronco deal tracker.

Edit this file to change what the tracker is looking for. Everything here
reflects the buyer's actual target: a new 4-door Bronco, bought around
December 2026, with a $21k paid-off trade-in.
"""
from __future__ import annotations

from datetime import date

# --- Buyer search criteria ---------------------------------------------

ZIP_CODE = "92706"  # Santa Ana, CA
SEARCH_AREAS = ["Orange County, CA", "Los Angeles County, CA", "Inland Empire, CA"]
SEARCH_RADIUS_MILES = 60

CONDITION = "new"
DOORS = 4
ROOF = "hardtop"

# Standard-tier trims: cheapest, most in-line with the budget.
PREFERRED_TRIMS = ["Big Bend", "Outer Banks"]

# Acceptable if the higher out-of-pocket cap below still covers it.
HIGHER_TRIMS = ["Black Diamond", "Badlands", "Wildtrak", "Everglades", "Heritage", "Heritage Limited"]

PREFERRED_COLORS = [
    "Shadow Black",
    "Agate Black",
    "Carbonized Gray",
    "Marsh Gray",
    "Cactus Gray",
    "Iconic Silver",
]

# Sticker-price band used to decide what's worth tracking at all.
PRICE_MIN = 40_000
PRICE_MAX = 45_000
# Loose ceiling for a higher trim - the real gate is the out-of-pocket cap
# below, this just keeps search results sane (no Raptor-tier prices).
HIGHER_TRIM_PRICE_MAX = 50_000

# --- Timeline -------------------------------------------------------------

# Buyer isn't purchasing before this date; tracking runs until then.
TARGET_BUY_DATE = date(2026, 12, 31)

# --- Trade-in ---------------------------------------------------------------

TRADE_IN_BASELINE_VALUE = 21_000  # paid off, no loan payoff to subtract
TRADE_IN_BASELINE_DATE = date(2026, 9, 12)

# Typical used-vehicle depreciation, expressed as a monthly rate. This is a
# rough planning estimate, not an appraisal (KBB/Carvana/CarMax offers will
# vary). ~1.2%/month is roughly a 14%/year curve, typical for a car that's
# already past its steepest depreciation years.
MONTHLY_DEPRECIATION_RATE = 0.012

# --- Out-of-pocket budget ---------------------------------------------------

# What you'll actually pay (cash or financed) after the trade-in is applied.
# Standard tier (Big Bend/Outer Banks): $25k-$29k. A higher trim: up to $30k.
OOP_CAP_STANDARD = 29_000
OOP_CAP_HIGHER_TRIM = 30_000

# California taxes the FULL vehicle price - it does NOT credit the trade-in
# value against sales tax (one of only a few states that doesn't). The
# trade-in only reduces what you owe out of pocket, not the taxable amount.
# 9.25% is the combined rate for zip 92706 (Santa Ana); dealer-city rates
# elsewhere in OC/LA/IE can differ by roughly +/-1.5 points, so treat this
# as an estimate and get the real number on the dealer's OTD quote.
SALES_TAX_RATE = 0.0925

# CA dealer doc fee is capped by law (CVC 11713.1) at $85. Add a rough
# estimate for DMV registration/title (varies with vehicle value/county).
DOC_FEE = 85
EST_REG_TITLE_FEES = 700


def oop_cap_for_trim(trim: str | None) -> int:
    """Out-of-pocket ceiling for a given trim."""
    return OOP_CAP_HIGHER_TRIM if trim in HIGHER_TRIMS else OOP_CAP_STANDARD


# --- Data files -------------------------------------------------------------

DATA_DIR = "data"
LISTINGS_FILE = f"{DATA_DIR}/listings.json"
TRADE_IN_FILE = f"{DATA_DIR}/trade_in.json"
REPORT_FILE = f"{DATA_DIR}/report.md"
REPORT_HTML_FILE = f"{DATA_DIR}/report.html"
REPORT_ARTIFACT_FILE = f"{DATA_DIR}/report_artifact.html"

# Days a listing sits with no price change/removal before we flag it as
# "stale" (i.e. actionable negotiating leverage).
STALE_DAYS_ON_MARKET = 21
