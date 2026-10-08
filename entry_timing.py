import pandas as pd

from indicators import Indicators
from structure import Structure


class EntryTimingEngine:
    """
    Entry timing engine for the 5m timeframe.

    The higher timeframes decide:
        - whether the market is worth trading
        - the main direction

    This engine decides:
        - whether the current 5m candle gives a valid entry
        - BREAKOUT or PULLBACK
        - the preferred entry price
        - the quality of the entry
    """

    MIN_SCORE = 60

    @staticmethod
    def _invalid(reason):
        return {
            "valid": False,
            "entry_method": None,
            "score": 0,
            "entry": None,
            "reason": reason,
        }

    @classmethod
    def analyze(
        cls,
        df5m,
        direction,
        technical=None
    ):
        # ----------------------------------------------------
        # Validate input
        # ----------------------------------------------------

        if df5m is None or df5m.empty:
            return cls._invalid(
                "5m market data unavailable."
            )

        if len(df5m) < 220:
            return cls._invalid(
                "Not enough 5m candles."
            )

        if direction not in {
            "LONG",
            "SHORT"
        }:
            return cls._invalid(
                "Invalid trading direction."
            )

        # ----------------------------------------------------
        # Enrich 5m data
        # ----------------------------------------------------

        data = Indicators.enrich(
            df5m.copy()
        )

        # Use the last CLOSED candle.
        # The newest candle may still be forming.
        current = data.iloc[-2]
        previous = data.iloc[-3]

        closed_data = data.iloc[-2]

        price = float(current["close"])

        atr = float(current["atr"])

        if pd.isna(atr) or atr <= 0:
            return cls._invalid(
                "Invalid 5m ATR."
            )

        # ----------------------------------------------------
        # 5m structure
        # ----------------------------------------------------

        levels = Structure.levels(
            closed_data,
            window=12
        )

        support = levels.get("support")
        resistance = levels.get("resistance")

        if support is None or resistance is None:
            return cls._invalid(
                "5m structure levels unavailable."
            )

        support = float(support)
        resistance = float(resistance)

        # ----------------------------------------------------
        # Common indicators
        # ----------------------------------------------------

        rsi = float(current["rsi"])
        macd = float(current["macd"])
        macd_signal = float(
            current["macd_signal"]
        )
        macd_histogram = float(
            current["macd_histogram"]
        )

        volume_ratio = float(
            current["volume_ratio"]
        )

        ema20 = float(current["ema20"])
        ema50 = float(current["ema50"])

        vwap = (
            float(current["vwap"])
            if pd.notna(current["vwap"])
            else None
        )

        candle_range = float(
            current["high"] -
            current["low"]
        )

        if candle_range <= 0:
            return cls._invalid(
                "Invalid 5m candle range."
            )

        candle_body = abs(
            float(current["close"]) -
            float(current["open"])
        )

        body_ratio = (
            candle_body / candle_range
        )

        # ----------------------------------------------------
        # Direction-specific validation
        # ----------------------------------------------------

        if direction == "LONG":

            bullish_candle = (
                current["close"] >
                current["open"]
            )

            trend_ok = (
                current["close"] >
                current["ema20"]
            )

            ema_alignment = (
                ema20 >= ema50
            )

            momentum_ok = (
                macd >= macd_signal and
                macd_histogram >= 0
            )

            rsi_ok = (
                50 <= rsi <= 75
            )

            vwap_ok = (
                vwap is None or
                price >= vwap
            )

        else:

            bullish_candle = (
                current["close"] <
                current["open"]
            )

            trend_ok = (
                current["close"] <
                current["ema20"]
            )

            ema_alignment = (
                ema20 <= ema50
            )

            momentum_ok = (
                macd <= macd_signal and
                macd_histogram <= 0
            )

            rsi_ok = (
                25 <= rsi <= 50
            )

            vwap_ok = (
                vwap is None or
                price <= vwap
            )

        # ----------------------------------------------------
        # BREAKOUT detection
        # ----------------------------------------------------

        breakout = False

        if direction == "LONG":
            breakout = (
                price > resistance and
                current["high"] > resistance
            )

        else:
            breakout = (
                price < support and
                current["low"] < support
            )

        breakout_score = 0

        if breakout:
            breakout_score += 25

            if trend_ok:
                breakout_score += 15

            if ema_alignment:
                breakout_score += 10

            if momentum_ok:
                breakout_score += 15

            if volume_ratio >= 1.3:
                breakout_score += 15

            if body_ratio >= 0.45:
                breakout_score += 10

            if rsi_ok:
                breakout_score += 5

            if vwap_ok:
                breakout_score += 5

        # ----------------------------------------------------
        # PULLBACK detection
        # ----------------------------------------------------

        pullback = False

        if direction == "LONG":

            was_below_ema = (
                previous["low"] <=
                previous["ema20"]
            )

            reclaimed_ema = (
                current["close"] >
                current["ema20"]
            )

            pullback = (
                was_below_ema and
                reclaimed_ema
            )

        else:

            was_above_ema = (
                previous["high"] >=
                previous["ema20"]
            )

            rejected_ema = (
                current["close"] <
                current["ema20"]
            )

            pullback = (
                was_above_ema and
                rejected_ema
            )

        pullback_score = 0

        if pullback:
            pullback_score += 20

            if trend_ok:
                pullback_score += 15

            if ema_alignment:
                pullback_score += 15

            if momentum_ok:
                pullback_score += 15

            if rsi_ok:
                pullback_score += 10

            if vwap_ok:
                pullback_score += 10

            if bullish_candle:
                pullback_score += 10

            if body_ratio >= 0.35:
                pullback_score += 5

        # ----------------------------------------------------
        # Avoid chasing extended moves
        # ----------------------------------------------------

        extension_limit = atr * 1.5

        if direction == "LONG":
            too_extended = (
                price >
                resistance + extension_limit
            )
        else:
            too_extended = (
                price <
                support - extension_limit
            )

        if too_extended:
            breakout_score = max(
                0,
                breakout_score - 25
            )

            pullback_score = max(
                0,
                pullback_score - 20
            )

        # ----------------------------------------------------
        # Select entry method
        # ----------------------------------------------------

        if (
            breakout and
            breakout_score >= cls.MIN_SCORE
        ):
            return {
                "valid": True,
                "entry_method": "BREAKOUT",
                "score": float(
                    min(breakout_score, 100)
                ),
                "entry": price,
                "price": price,
                "atr": atr,
                "support": support,
                "resistance": resistance,
                "rsi": rsi,
                "volume_ratio": volume_ratio,
                "reason": (
                    "5m breakout confirmed with "
                    "trend, momentum and volume."
                ),
            }

        if (
            pullback and
            pullback_score >= cls.MIN_SCORE
        ):
            return {
                "valid": True,
                "entry_method": "PULLBACK",
                "score": float(
                    min(pullback_score, 100)
                ),
                "entry": price,
                "price": price,
                "atr": atr,
                "support": support,
                "resistance": resistance,
                "rsi": rsi,
                "volume_ratio": volume_ratio,
                "reason": (
                    "5m pullback reversal confirmed "
                    "with trend and momentum."
                ),
            }

        # ----------------------------------------------------
        # Candidate detected but timing not confirmed
        # ----------------------------------------------------

        best_score = max(
            breakout_score,
            pullback_score
        )

        if best_score > 0:
            if breakout_score >= pullback_score:
                method = "BREAKOUT"
            else:
                method = "PULLBACK"

            return {
                "valid": False,
                "entry_method": method,
                "score": float(
                    min(best_score, 100)
                ),
                "entry": price,
                "price": price,
                "atr": atr,
                "support": support,
                "resistance": resistance,
                "rsi": rsi,
                "volume_ratio": volume_ratio,
                "reason": (
                    "5m setup is forming but entry "
                    "confirmation is not strong enough."
                ),
            }

        return {
            "valid": False,
            "entry_method": None,
            "score": 0,
            "entry": price,
            "price": price,
            "atr": atr,
            "support": support,
            "resistance": resistance,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
            "reason": (
                "No valid 5m breakout or pullback "
                "entry detected."
            ),
        }
