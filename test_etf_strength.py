import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from etf_strength import (
    _is_stock_holding,
    build_metric_history,
    build_snapshots,
    rank_groups_for_session,
    validate_actual_close,
    validate_completed_session,
)


def metric_frame(session: date, performance: float, extension: float = 2.0) -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "perf_1m": performance,
            "perf_3m": performance,
            "perf_6m": performance,
            "adrp": 5.0,
            "atrp": 4.0,
            "average_volume_10d": 1_000_000,
            "average_dollar_volume_30d": 100_000_000,
            "extension": extension,
            "is_tight": True,
            "coil_setup": "3D",
            "rmv_15d": 10.0,
        }],
        index=[pd.Timestamp(session)],
    )


class EtfStrengthTests(unittest.TestCase):
    def test_multiple_etfs_confirm_one_group_instead_of_using_multiple_slots(self):
        session = date(2026, 9, 28)
        universe = pd.DataFrame([
            {"Ticker": "HACK", "Group": "Cybersecurity", "Description": "Broad"},
            {"Ticker": "BUG", "Group": "Cybersecurity", "Description": "Pure play"},
            {"Ticker": "CIBR", "Group": "Cybersecurity", "Description": "Security"},
            {"Ticker": "AIQ", "Group": "AI", "Description": "AI"},
        ])
        histories = {
            "HACK": metric_frame(session, 30),
            "BUG": metric_frame(session, 28),
            "CIBR": metric_frame(session, 27),
            "AIQ": metric_frame(session, 20),
        }
        groups = rank_groups_for_session(histories, universe, session, "perf_1m", 2)
        self.assertEqual([group["group"] for group in groups], ["Cybersecurity", "AI"])
        self.assertEqual(groups[0]["member_count"], 3)
        self.assertEqual({row["symbol"] for row in groups[0]["members"]}, {"HACK", "BUG", "CIBR"})

    def test_metric_history_uses_adjusted_close_for_performance(self):
        index = pd.bdate_range("2025-12-01", periods=180)
        raw_close = pd.Series(range(100, 280), index=index, dtype=float)
        history = pd.DataFrame({
            "high": raw_close + 2,
            "low": raw_close - 2,
            "close": raw_close,
            "adj_close": raw_close * 2,
            "volume": 1_000_000,
        })
        metrics = build_metric_history(history)
        target = index[-1] - pd.DateOffset(months=1)
        prior = history.loc[history.index <= target, "adj_close"].iloc[-1]
        expected = 100 * (history["adj_close"].iloc[-1] / prior - 1)
        self.assertAlmostEqual(metrics["perf_1m"].iloc[-1], expected)

    def test_stale_market_close_is_rejected(self):
        histories = {"SPY": pd.DataFrame({"close": [100]}, index=[pd.Timestamp("2026-09-25")])}
        with self.assertRaises(RuntimeError):
            validate_actual_close(histories, date(2026, 9, 28))

    def test_incomplete_current_session_is_rejected(self):
        morning_in_new_york = datetime(2026, 9, 29, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        with self.assertRaises(RuntimeError):
            validate_completed_session(date(2026, 9, 29), morning_in_new_york)
        validate_completed_session(date(2026, 9, 28), morning_in_new_york)

    def test_historical_snapshot_uses_actual_close_date(self):
        session = date(2026, 9, 25)
        universe = pd.DataFrame([{"Ticker": "AIQ", "Group": "AI", "Description": "AI"}])
        snapshots = build_snapshots({"AIQ": metric_frame(session, 20)}, universe, [session], 10)
        self.assertEqual(snapshots[0]["date"], "2026-09-25")

    def test_non_stock_holdings_are_removed(self):
        funds = {"HACK", "BUG"}
        self.assertTrue(_is_stock_holding("CRWD", "CrowdStrike Holdings", funds))
        self.assertFalse(_is_stock_holding("USD", "U.S. Dollar Cash", funds))
        self.assertFalse(_is_stock_holding("HACK", "ETFMG Prime Cyber Security ETF", funds))
        self.assertFalse(_is_stock_holding("SWP1", "Index Swap", funds))


if __name__ == "__main__":
    unittest.main()
