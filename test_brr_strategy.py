
"""Unit tests for the standalone BRR strategy."""

import unittest

import pandas as pd

from brr_strategy import BRRStrategy


def make_candles(closes, opens=None, highs=None, lows=None, volumes=None):
    """Create deterministic OHLCV candles for unit tests."""
    count = len(closes)
    opens = opens or closes[:]
    highs = highs or [
        max(o, c) + 0.5 for o, c in zip(opens, closes)
    ]
    lows = lows or [
        min(o, c) - 0.5 for o, c in zip(opens, closes)
    ]
    volumes = volumes or [100.0] * count

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


class TestBRRStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = BRRStrategy()

    def test_strategy_is_disabled_by_default(self):
        self.assertFalse(BRRStrategy.ENABLED)

    def test_invalid_or_insufficient_data_returns_no_signal(self):
        result = self.strategy.analyze(
            pd.DataFrame(),
            pd.DataFrame(),
            symbol="FET/USDT:USDT",
        )

        self.assertEqual(result["status"], "NO_SIGNAL")
        self.assertEqual(
            result["reason"],
            "INSUFFICIENT_15M_DATA",
        )
        self.assertFalse(result["execution_allowed"])

    def test_closed_candles_excludes_latest_row(self):
        df = make_candles([10, 11, 12, 13])

        closed = BRRStrategy._closed_candles(df)

        self.assertEqual(len(closed), 3)
        self.assertEqual(float(closed.iloc[-1]["close"]), 12.0)

    def test_valid_long_breakout_retest_is_detected(self):
        df = make_candles(
            closes=[98.0, 99.0, 99.5, 101.0, 102.0, 101.0],
            opens=[98.5, 98.8, 99.2, 99.6, 101.0, 100.2],
            highs=[99.0, 99.5, 100.0, 101.5, 102.5, 101.5],
            lows=[97.5, 98.5, 99.0, 99.4, 100.5, 99.8],
        )

        setup = BRRStrategy._find_setup(
            df15m=df,
            level=100.0,
            direction="LONG",
            atr=2.0,
        )

        self.assertIsNotNone(setup)
        self.assertEqual(setup["level"], 100.0)
        self.assertEqual(setup["entry"], 101.0)

    def test_failed_breakout_is_rejected(self):
        df = make_candles(
            closes=[98.0, 99.0, 99.5, 101.0, 99.7, 101.0],
            opens=[98.5, 98.8, 99.2, 99.6, 101.0, 100.2],
            highs=[99.0, 99.5, 100.0, 101.5, 101.5, 101.5],
            lows=[97.5, 98.5, 99.0, 99.4, 99.4, 99.8],
        )

        setup = BRRStrategy._find_setup(
            df15m=df,
            level=100.0,
            direction="LONG",
            atr=2.0,
        )

        self.assertIsNone(setup)

    def test_long_targets_are_calculated_correctly(self):
        result = self.strategy._signal(
            symbol="FET/USDT:USDT",
            direction="LONG",
            entry=101.0,
            stop=99.0,
            risk=2.0,
            level=100.0,
            trend="BULLISH",
            volume_ratio=1.2,
            next_level=106.0,
            reason="Unit test",
        )

        self.assertEqual(result["target_1_5R"], 104.0)
        self.assertEqual(result["target_2R"], 105.0)
        self.assertEqual(result["next_hourly_level"], 106.0)
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["status"], "SHADOW_SIGNAL")

    def test_short_targets_are_calculated_correctly(self):
        result = self.strategy._signal(
            symbol="NEAR/USDT:USDT",
            direction="SHORT",
            entry=100.0,
            stop=102.0,
            risk=2.0,
            level=101.0,
            trend="BEARISH",
            volume_ratio=1.1,
            next_level=95.0,
            reason="Unit test",
        )

        self.assertEqual(result["target_1_5R"], 97.0)
        self.assertEqual(result["target_2R"], 96.0)
        self.assertEqual(result["next_hourly_level"], 95.0)
        self.assertFalse(result["execution_allowed"])

    def test_short_setup_rejects_close_above_level(self):
        df = make_candles(
            closes=[102.0, 101.0, 100.5, 99.0, 98.0, 101.0],
            opens=[101.5, 101.2, 100.8, 100.4, 99.0, 99.5],
            highs=[102.5, 101.5, 101.0, 100.5, 99.5, 101.5],
            lows=[101.0, 100.5, 100.0, 98.5, 97.5, 98.5],
        )

        setup = BRRStrategy._find_setup(
            df15m=df,
            level=100.0,
            direction="SHORT",
            atr=2.0,
        )

        self.assertIsNone(setup)


if __name__ == "__main__":
    unittest.main(verbosity=2)
