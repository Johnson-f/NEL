import unittest

import pandas as pd

from tight_nel import calculate_coil_metrics, find_tight_nel


def make_history(tight: bool = True) -> pd.DataFrame:
    closes = [100 + index * 0.2 for index in range(25)]
    if tight:
        closes.extend([105.0, 105.2, 105.1, 105.3, 105.4])
        ranges = [4.0] * 25 + [0.9, 0.8, 0.7, 0.8, 0.6]
    else:
        closes.extend([105.0, 108.0, 111.0, 114.0, 117.0])
        ranges = [4.0] * 30
    return pd.DataFrame(
        {
            "high": [close + bar_range / 2 for close, bar_range in zip(closes, ranges)],
            "low": [close - bar_range / 2 for close, bar_range in zip(closes, ranges)],
            "close": closes,
        }
    )


class TightNelTests(unittest.TestCase):
    def test_fast_coil_passes_clustered_contracting_prices(self):
        metrics = calculate_coil_metrics(make_history(tight=True))
        self.assertIsNotNone(metrics)
        self.assertTrue(metrics["is_tight_nel"])
        self.assertIn(metrics["coil_setup"], {"3D", "5D", "3D + 5D"})
        self.assertLessEqual(metrics["coil_range_5d_atr"], 2.5)
        self.assertLessEqual(metrics["true_range_ratio_5d"], 0.85)

    def test_fast_coil_rejects_wide_drifting_prices(self):
        metrics = calculate_coil_metrics(make_history(tight=False))
        self.assertIsNotNone(metrics)
        self.assertFalse(metrics["is_tight_nel"])

    def test_only_passing_nel_rows_are_returned(self):
        nel = pd.DataFrame(
            [
                {"name": "TIGHT", "momentum_score": 50.0},
                {"name": "WIDE", "momentum_score": 60.0},
            ]
        )
        histories = {"TIGHT": make_history(tight=True), "WIDE": make_history(tight=False)}
        result, errors = find_tight_nel(nel, histories=histories)
        self.assertEqual(list(result["name"]), ["TIGHT"])
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
