import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bronco_tracker import config, deals, storage, trade_in  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
