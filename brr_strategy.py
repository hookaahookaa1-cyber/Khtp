
"""
BRR Strategy — Breakout, Retest, Rejection
Version: 0.1.0

Standalone signal-analysis module.
- Entry timeframe: 15m
- Structure timeframe: 1h
- Closed candles only
- No exchange connection and no order execution
- Disabled by default
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

import pandas as pd


BRR_ENABLED = False
BRR_VERSION = "0.1.0"


@dataclass
class BRRSignal:
    strategy: str
    version: str
    symbol: Optional[str]
    direction: str
    status: str
    entry: float
    stop: float
    risk_distance: float
    target_1_5R: float
    target_2R: float
    next_hourly_level: Optional[float]
    breakout_level: float
    trend_1h: str
    volume_ratio: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BRRStrategy:
    """
    Detects a breakout followed by its first retest and rejection.

    This class only analyses supplied OHLCV data. It does not place
    orders, connect to an exchange, or alter another strategy.
    """

    ENABLED = BRR_ENABLED
    VERSION = BRR_VERSION

    ENTRY_TIMEFRAME = "15m"
    STRUCTURE_TIMEFRAME = "1h"

    MIN_15M_CANDLES = 80
    MIN_1H_CANDLES = 30

    LEVEL_LOOKBACK = 20
    PIVOT_LOOKBACK = 60
    BREAKOUT_LOOKBACK = 12

    ATR_PERIOD = 14
    EMA_FAST = 20
    EMA_SLOW = 50
    VOLUME_PERIOD = 20

    # A retest can touch within this ATR-scaled distance.
    RETEST_ATR_TOLERANCE = 0.25

    # The breakout must close beyond the level by this ATR fraction.
    BREAKOUT_ATR_BUFFER = 0.10

    # Stop is placed beyond the rejection candle with an ATR buffer.
    STOP_ATR_BUFFER = 0.20

    # Countertrend exception requires stronger volume confirmation.
    COUNTERTREND_VOLUME_RATIO = 1.50

    REQUIRED_COLUMNS = {
        "open", "high", "low", "close", "volume"
    }

    @staticmethod
    def _valid_frame(df: pd.DataFrame, minimum: int) -> bool:
        if df is None or not isinstance(df, pd.DataFrame):
            return False

        if len(df) < minimum:
            return False

        if not BRRStrategy.REQUIRED_COLUMNS.issubset(df.columns):
            return False

        return True

    @staticmethod
    def _closed_candles(df: pd.DataFrame) -> pd.DataFrame:
        """
        The newest OHLCV row is assumed to be the still-forming candle.
        Remove it so signals use closed candles only.
        """
        result = df.copy()

        for column in BRRStrategy.REQUIRED_COLUMNS:
            result[column] = pd.to_numeric(
                result[column], errors="coerce"
            )

        result = result.dropna(
            subset=list(BRRStrategy.REQUIRED_COLUMNS)
        ).reset_index(drop=True)

        if len(result) < 2:
            return result.iloc[0:0]

        return result.iloc[:-1].reset_index(drop=True)

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        previous_close = df["close"].shift(1)

        true_range = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - previous_close).abs(),
                (df["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return true_range.rolling(
            period, min_periods=period
        ).mean()

    @staticmethod
    def _hourly_trend(df1h: pd.DataFrame) -> Dict[str, Any]:
        close = df1h["close"]

        ema_fast = close.ewm(
            span=BRRStrategy.EMA_FAST,
            adjust=False,
        ).mean()

        ema_slow = close.ewm(
            span=BRRStrategy.EMA_SLOW,
            adjust=False,
        ).mean()

        last_close = float(close.iloc[-1])
        fast = float(ema_fast.iloc[-1])
        slow = float(ema_slow.iloc[-1])

        if fast > slow and last_close >= fast:
            trend = "BULLISH"
        elif fast < slow and last_close <= fast:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        return {
            "trend": trend,
            "close": last_close,
            "ema_fast": fast,
            "ema_slow": slow,
        }

    @staticmethod
    def _volume_ratio(
        df: pd.DataFrame,
        period: int = 20,
    ) -> float:
        if len(df) < period + 1:
            return 0.0

        baseline = float(
            df["volume"].iloc[-period - 1:-1].mean()
        )
        current = float(df["volume"].iloc[-1])

        if baseline <= 0:
            return 0.0

        return current / baseline

    @staticmethod
    def _hourly_pivots(
        df1h: pd.DataFrame,
    ) -> List[Dict[str, float]]:
        """
        Return confirmed local hourly swing highs/lows.
        The two candles on either side are required for confirmation.
        """
        pivots = []
        start = max(2, len(df1h) - BRRStrategy.PIVOT_LOOKBACK)
        end = len(df1h) - 2

        for i in range(start, end):
            high = float(df1h["high"].iloc[i])
            low = float(df1h["low"].iloc[i])

            left_highs = df1h["high"].iloc[i - 2:i]
            right_highs = df1h["high"].iloc[i + 1:i + 3]

            left_lows = df1h["low"].iloc[i - 2:i]
            right_lows = df1h["low"].iloc[i + 1:i + 3]

            if (
                high > float(left_highs.max())
                and high >= float(right_highs.max())
            ):
                pivots.append({
                    "type": "RESISTANCE",
                    "price": high,
                })

            if (
                low < float(left_lows.min())
                and low <= float(right_lows.min())
            ):
                pivots.append({
                    "type": "SUPPORT",
                    "price": low,
                })

        return pivots

    @staticmethod
    def _next_opposing_level(
        direction: str,
        entry: float,
        pivots: List[Dict[str, float]],
    ) -> Optional[float]:
        if direction == "LONG":
            candidates = [
                p["price"]
                for p in pivots
                if p["type"] == "RESISTANCE"
                and p["price"] > entry
            ]

            return min(candidates) if candidates else None

        candidates = [
            p["price"]
            for p in pivots
            if p["type"] == "SUPPORT"
            and p["price"] < entry
        ]

        return max(candidates) if candidates else None

    @staticmethod
    def _find_setup(
        df15m: pd.DataFrame,
        level: float,
        direction: str,
        atr: float,
    ) -> Optional[Dict[str, float]]:
        """
        Require a prior close beyond the level, followed by a retest
        and rejection on the latest closed candle.

        The latest closed candle must be the rejection candle.
        A close back through the level invalidates the setup.
        """
        if len(df15m) < 4 or atr <= 0:
            return None

        tolerance = atr * BRRStrategy.RETEST_ATR_TOLERANCE
        breakout_buffer = atr * BRRStrategy.BREAKOUT_ATR_BUFFER

        latest = df15m.iloc[-1]
        previous = df15m.iloc[-2]

        # The latest candle must show rejection in the breakout direction.
        if direction == "LONG":
            retest = (
                float(latest["low"]) <= level + tolerance
                and float(latest["low"]) >= level - tolerance
                and float(latest["close"]) > level
                and float(latest["close"]) > float(latest["open"])
            )
        else:
            retest = (
                float(latest["high"]) >= level - tolerance
                and float(latest["high"]) <= level + tolerance
                and float(latest["close"]) < level
                and float(latest["close"]) < float(latest["open"])
            )

        if not retest:
            return None

        # Search backwards for a breakout that happened before the retest.
        first_index = max(
            1, len(df15m) - BRRStrategy.BREAKOUT_LOOKBACK - 1
        )
        breakout_index = None

        for i in range(len(df15m) - 2, first_index - 1, -1):
            previous_close = float(df15m["close"].iloc[i - 1])
            current_close = float(df15m["close"].iloc[i])

            if direction == "LONG":
                crossed = (
                    previous_close <= level
                    and current_close > level + breakout_buffer
                )
            else:
                crossed = (
                    previous_close >= level
                    and current_close < level - breakout_buffer
                )

            if crossed:
                breakout_index = i
                break

        if breakout_index is None:
            return None

        # Between breakout and retest, price must not close back through
        # the level. This also prevents accepting a failed breakout.
        interim = df15m.iloc[breakout_index + 1:-1]

        if not interim.empty:
            if direction == "LONG":
                if (interim["close"] <= level).any():
                    return None
            else:
                if (interim["close"] >= level).any():
                    return None

        return {
            "level": float(level),
            "retest_low": float(latest["low"]),
            "retest_high": float(latest["high"]),
            "entry": float(latest["close"]),
        }

    def analyze(
        self,
        df15m: pd.DataFrame,
        df1h: pd.DataFrame,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyse data and return a structured result.

        This method can analyse signals while ENABLED is False, but the
        disabled flag means a caller must not treat the result as an
        instruction to trade.
        """
        if not self._valid_frame(
            df15m, self.MIN_15M_CANDLES
        ):
            return self._no_signal(
                symbol, "INSUFFICIENT_15M_DATA"
            )

        if not self._valid_frame(
            df1h, self.MIN_1H_CANDLES
        ):
            return self._no_signal(
                symbol, "INSUFFICIENT_1H_DATA"
            )

        candles15 = self._closed_candles(df15m)
        candles1h = self._closed_candles(df1h)

        if (
            len(candles15) < self.MIN_15M_CANDLES - 1
            or len(candles1h) < self.MIN_1H_CANDLES - 1
        ):
            return self._no_signal(
                symbol, "INSUFFICIENT_CLOSED_CANDLES"
            )

        atr_series = self._atr(
            candles15, self.ATR_PERIOD
        )
        atr = float(atr_series.iloc[-1])

        if pd.isna(atr) or atr <= 0:
            return self._no_signal(symbol, "INVALID_ATR")

        trend_data = self._hourly_trend(candles1h)
        trend = trend_data["trend"]

        # Structure levels are calculated from prior closed hourly bars.
        structure = candles1h.iloc[:-1].tail(
            self.LEVEL_LOOKBACK
        )

        if len(structure) < self.LEVEL_LOOKBACK:
            return self._no_signal(
                symbol, "INSUFFICIENT_STRUCTURE_DATA"
            )

        resistance = float(structure["high"].max())
        support = float(structure["low"].min())

        volume_ratio = self._volume_ratio(candles15)
        last_close = float(candles15["close"].iloc[-1])

        pivots = self._hourly_pivots(candles1h)

        # Check the recent resistance breakout/retest first.
        long_setup = self._find_setup(
            candles15, resistance, "LONG", atr
        )

        if long_setup:
            # Trend alignment is preferred. Countertrend entries require
            # price above hourly EMA20 and unusually strong volume.
            aligned = trend == "BULLISH"
            measured_exception = (
                trend == "BEARISH"
                and trend_data["close"] > trend_data["ema_fast"]
                and volume_ratio >= self.COUNTERTREND_VOLUME_RATIO
            )

            if trend == "NEUTRAL":
                aligned = (
                    trend_data["close"] >= trend_data["ema_fast"]
                    and volume_ratio >= 1.0
                )

            if aligned or measured_exception:
                entry = long_setup["entry"]
                stop = long_setup["retest_low"] - (
                    atr * self.STOP_ATR_BUFFER
                )
                risk = entry - stop

                if risk > 0 and stop > 0:
                    next_level = self._next_opposing_level(
                        "LONG", entry, pivots
                    )

                    return self._signal(
                        symbol=symbol,
                        direction="LONG",
                        entry=entry,
                        stop=stop,
                        risk=risk,
                        level=long_setup["level"],
                        trend=trend,
                        volume_ratio=volume_ratio,
                        next_level=next_level,
                        reason=(
                            "15m breakout, first retest and bullish "
                            "rejection confirmed; hourly trend filter passed."
                        ),
                    )

        short_setup = self._find_setup(
            candles15, support, "SHORT", atr
        )

        if short_setup:
            aligned = trend == "BEARISH"
            measured_exception = (
                trend == "BULLISH"
                and trend_data["close"] < trend_data["ema_fast"]
                and volume_ratio >= self.COUNTERTREND_VOLUME_RATIO
            )

            if trend == "NEUTRAL":
                aligned = (
                    trend_data["close"] <= trend_data["ema_fast"]
                    and volume_ratio >= 1.0
                )

            if aligned or measured_exception:
                entry = short_setup["entry"]
                stop = short_setup["retest_high"] + (
                    atr * self.STOP_ATR_BUFFER
                )
                risk = stop - entry

                if risk > 0:
                    next_level = self._next_opposing_level(
                        "SHORT", entry, pivots
                    )

                    return self._signal(
                        symbol=symbol,
                        direction="SHORT",
                        entry=entry,
                        stop=stop,
                        risk=risk,
                        level=short_setup["level"],
                        trend=trend,
                        volume_ratio=volume_ratio,
                        next_level=next_level,
                        reason=(
                            "15m breakdown, first retest and bearish "
                            "rejection confirmed; hourly trend filter passed."
                        ),
                    )

        return self._no_signal(
            symbol,
            "NO_CONFIRMED_BRR_SETUP",
            details={
                "trend_1h": trend,
                "support_1h": support,
                "resistance_1h": resistance,
                "volume_ratio": round(volume_ratio, 3),
                "enabled": self.ENABLED,
            },
        )

    def _signal(
        self,
        symbol: Optional[str],
        direction: str,
        entry: float,
        stop: float,
        risk: float,
        level: float,
        trend: str,
        volume_ratio: float,
        next_level: Optional[float],
        reason: str,
    ) -> Dict[str, Any]:
        if direction == "LONG":
            target_1_5r = entry + 1.5 * risk
            target_2r = entry + 2.0 * risk
        else:
            target_1_5r = entry - 1.5 * risk
            target_2r = entry - 2.0 * risk

        signal = BRRSignal(
            strategy="BRR",
            version=self.VERSION,
            symbol=symbol,
            direction=direction,
            status="SHADOW_SIGNAL",
            entry=round(entry, 10),
            stop=round(stop, 10),
            risk_distance=round(risk, 10),
            target_1_5R=round(target_1_5r, 10),
            target_2R=round(target_2r, 10),
            next_hourly_level=(
                round(next_level, 10)
                if next_level is not None else None
            ),
            breakout_level=round(level, 10),
            trend_1h=trend,
            volume_ratio=round(volume_ratio, 3),
            reason=reason,
        ).to_dict()

        # Signal generation is informational only. It never executes trades.
        signal["enabled"] = self.ENABLED
        signal["execution_allowed"] = False
        signal["target_comparison"] = {
            "1.5R": signal["target_1_5R"],
            "2R": signal["target_2R"],
            "next_hourly_level": signal["next_hourly_level"],
        }

        return signal

    def _no_signal(
        self,
        symbol: Optional[str],
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = {
            "strategy": "BRR",
            "version": self.VERSION,
            "symbol": symbol,
            "status": "NO_SIGNAL",
            "reason": reason,
            "enabled": self.ENABLED,
            "execution_allowed": False,
        }

        if details:
            result.update(details)

        return result
