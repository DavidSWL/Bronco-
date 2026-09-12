import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bronco_tracker import budget, config, deals, storage, trade_in  # noqa: E402


class TrackerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class StorageTests(TrackerTestCase):
    def test_upsert_new_listing_sets_first_and_last_seen(self):
        record = storage.upsert_listing("d1", {"dealer": "A", "trim": "Big Bend", "price": 44000})
        self.assertEqual(record["first_seen"], date.today().isoformat())
        self.assertEqual(record["last_seen"], date.today().isoformat())
        self.assertEqual(record["status"], "active")
        self.assertEqual(len(record["price_history"]), 1)

    def test_upsert_existing_listing_appends_price_history_on_change(self):
        storage.upsert_listing("d1", {"dealer": "A", "trim": "Big Bend", "price": 44000})
        storage.upsert_listing("d1", {"dealer": "A", "trim": "Big Bend", "price": 43000})
        listings = storage.load_listings()
        self.assertEqual(len(listings["d1"]["price_history"]), 2)
        self.assertEqual(listings["d1"]["price_history"][-1]["price"], 43000)

    def test_upsert_same_price_does_not_duplicate_history(self):
        storage.upsert_listing("d1", {"dealer": "A", "price": 44000})
        storage.upsert_listing("d1", {"dealer": "A", "price": 44000})
        listings = storage.load_listings()
        self.assertEqual(len(listings["d1"]["price_history"]), 1)

    def test_sweep_missing_marks_removed(self):
        storage.upsert_listing("d1", {"dealer": "A", "price": 44000})
        storage.upsert_listing("d2", {"dealer": "B", "price": 45000})
        removed = storage.sweep_missing({"d1"})
        self.assertEqual(removed, ["d2"])
        self.assertEqual(storage.load_listings()["d2"]["status"], "removed")
        self.assertEqual(storage.load_listings()["d1"]["status"], "active")

    def test_days_on_market_uses_today_for_active_listing(self):
        record = storage.upsert_listing("d1", {"price": 44000})
        record["first_seen"] = (date.today() - timedelta(days=10)).isoformat()
        storage.save_listings({"d1": record})
        self.assertEqual(storage.days_on_market(storage.load_listings()["d1"]), 10)


class DealsTests(TrackerTestCase):
    def test_cheapest_listing_scores_highest_among_peers(self):
        storage.upsert_listing("expensive", {"trim": "Big Bend", "price": 47000})
        storage.upsert_listing("cheap", {"trim": "Big Bend", "price": 41000})
        storage.upsert_listing("mid", {"trim": "Big Bend", "price": 44000})
        ranked = deals.rank_deals()
        self.assertEqual(ranked[0]["id"], "cheap")
        self.assertEqual(ranked[-1]["id"], "expensive")

    def test_price_drop_detected(self):
        storage.upsert_listing("d1", {"trim": "Big Bend", "price": 45000})
        storage.upsert_listing("d1", {"trim": "Big Bend", "price": 43000})
        listings = storage.load_listings()
        self.assertEqual(deals.price_drop(listings["d1"]), 2000)

    def test_trend_summary_counts_only_active(self):
        storage.upsert_listing("d1", {"trim": "Big Bend", "price": 44000})
        storage.upsert_listing("d2", {"trim": "Big Bend", "price": 46000})
        storage.mark_removed("d2", status="sold")
        trends = deals.trend_summary()
        self.assertEqual(trends["count"], 1)
        self.assertEqual(trends["sold_or_removed_count"], 1)


class TradeInTests(TrackerTestCase):
    def test_value_depreciates_over_time(self):
        ti = {
            "baseline_value": 21000,
            "baseline_date": "2026-09-12",
            "monthly_depreciation_rate": 0.012,
        }
        value_now = trade_in.project_value(date(2026, 9, 12), ti)
        value_later = trade_in.project_value(date(2026, 12, 31), ti)
        self.assertEqual(value_now, 21000)
        self.assertLess(value_later, value_now)

    def test_projection_to_target_shape(self):
        result = trade_in.projection_to_target(
            {
                "baseline_value": 21000,
                "baseline_date": "2026-09-12",
                "monthly_depreciation_rate": 0.012,
            },
            target=config.TARGET_BUY_DATE,
        )
        self.assertIn("projected_at_target", result)
        self.assertLessEqual(result["projected_at_target"], result["baseline_value"])


class BudgetTests(unittest.TestCase):
    def test_ca_tax_applies_to_full_price_not_net_of_trade(self):
        result = budget.estimate_out_of_pocket(44169, "Big Bend", trade_in_value=20099)
        expected_tax = round(44169 * config.SALES_TAX_RATE)
        expected_fees = config.DOC_FEE + config.EST_REG_TITLE_FEES
        expected_otd = 44169 + expected_tax + expected_fees
        self.assertEqual(result["estimated_otd"], expected_otd)
        self.assertEqual(result["out_of_pocket"], expected_otd - 20099)

    def test_standard_trim_uses_standard_cap(self):
        result = budget.estimate_out_of_pocket(45000, "Outer Banks", trade_in_value=20000)
        self.assertEqual(result["out_of_pocket_cap"], config.OOP_CAP_STANDARD)

    def test_higher_trim_uses_higher_cap(self):
        result = budget.estimate_out_of_pocket(45000, "Badlands", trade_in_value=20000)
        self.assertEqual(result["out_of_pocket_cap"], config.OOP_CAP_HIGHER_TRIM)

    def test_within_budget_flag(self):
        cheap = budget.estimate_out_of_pocket(30000, "Big Bend", trade_in_value=20000)
        pricey = budget.estimate_out_of_pocket(60000, "Big Bend", trade_in_value=20000)
        self.assertTrue(cheap["within_budget"])
        self.assertFalse(pricey["within_budget"])
        self.assertGreater(pricey["over_by"], 0)
        self.assertEqual(cheap["over_by"], 0)

    def test_email_template_keeps_price_and_trade_separate(self):
        record = {"trim": "Big Bend", "color_exterior": "Marsh Gray", "stock_number": "FB1", "dealer": "Test Ford"}
        email = budget.email_template(record, trade_in_value=21000)
        self.assertIn("FB1", email["subject"])
        self.assertIn("out-the-door", email["body"].lower())
        self.assertIn("21,000", email["body"])
        self.assertTrue(email["mailto"].startswith("mailto:?subject="))


if __name__ == "__main__":
    unittest.main()
