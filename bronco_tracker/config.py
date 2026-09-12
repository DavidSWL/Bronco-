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

# Preferred trims, cheapest-first. A higher trim is acceptable if the price
# still falls inside PRICE_RANGE.
PREFERRED_TRIMS = ["Big Bend", "Outer Banks", "Black Diamond", "Badlands"]

PREFERRED_COLORS = [
    "Shadow Black",
    "Agate Black",
    "Carbonized Gray",
    "Marsh Gray",
    "Cactus Gray",
    "Iconic Silver",
]

PRICE_MIN = 40_000
PRICE_MAX = 48_000

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

# --- Data files -------------------------------------------------------------

DATA_DIR = "data"
LISTINGS_FILE = f"{DATA_DIR}/listings.json"
TRADE_IN_FILE = f"{DATA_DIR}/trade_in.json"
REPORT_FILE = f"{DATA_DIR}/report.md"

# Days a listing sits with no price change/removal before we flag it as
# "stale" (i.e. actionable negotiating leverage).
STALE_DAYS_ON_MARKET = 21
