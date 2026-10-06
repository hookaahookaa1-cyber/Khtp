import pandas as pd

from indicators import Indicators
from structure import Structure


class TechnicalEngine:

    @staticmethod
    def analyze(df15, df1h, df4h):

        # ----------------------------------------------------
        # Validate data
        # ----------------------------------------------------

        if (
            df15 is None or
            df1h is None or
            df4h is None
        ):
            return None

        if (
            len(df15) < 220 or
            len(df1h) < 220 or
            len(df4h) < 220
        ):
            return None

        # ----------------------------------------------------
        # Enrich all timeframes
        # ----------------------------------------------------

        a15 = Indicators.enrich(df15)
        a1 = Indicators.enrich(df1h)
        a4 = Indicators.enrich(df4h)

        # Use the last CLOSED candle.
        # The newest candle can still be forming.
        x = a15.iloc[-2]
        h1 = a1.iloc[-2]
        h4 = a4.iloc[-2]

        # ----------------------------------------------------
        # Market structure
        # ----------------------------------------------------

        levels = Structure.levels(
            a15.iloc[:-1]
        )

        price = float(x["close"])

        resistance = float(
            levels["resistance"]
        )

        support = float(
            levels["support"]
        )

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        long_score = 0
        short_score = 0

        # ====================================================
        # 15M TREND
        # ====================================================

        if x["ema20"] > x["ema50"]:
            long_score += 10

        elif x["ema20"] < x["ema50"]:
            short_score += 10

        # ====================================================
        # 1H TREND
        # ====================================================

        if h1["close"] > h1["ema20"]:
            long_score += 12

        elif h1["close"] < h1["ema20"]:
            short_score += 12

        if h1["ema20"] > h1["ema50"]:
            long_score += 8

        elif h1["ema20"] < h1["ema50"]:
            short_score += 8

        # ====================================================
        # 4H TREND
        # ====================================================

        if h4["close"] > h4["ema20"]:
            long_score += 10

        elif h4["close"] < h4["ema20"]:
            short_score += 10

        if h4["ema20"] > h4["ema50"]:
            long_score += 8

        elif h4["ema20"] < h4["ema50"]:
            short_score += 8

        # ====================================================
        # RSI
        # ====================================================

        if 55 <= x["rsi"] <= 72:
            long_score += 10

        elif 28 <= x["rsi"] <= 45:
            short_score += 10

        # ====================================================
        # MACD
        # ====================================================

        if x["macd"] > x["macd_signal"]:
            long_score += 8

        elif x["macd"] < x["macd_signal"]:
            short_score += 8

        # ====================================================
        # MACD HISTOGRAM
        # ====================================================

        if x["macd_histogram"] > 0:
            long_score += 4

        elif x["macd_histogram"] < 0:
            short_score += 4

        # ====================================================
        # ADX / TREND STRENGTH
        # ====================================================

        if x["adx"] >= 20:

            if x["ema20"] > x["ema50"]:
                long_score += 8

            elif x["ema20"] < x["ema50"]:
                short_score += 8

        # ====================================================
        # VOLUME
        # ====================================================

        if x["volume_ratio"] >= 1.3:

            if x["close"] > x["open"]:
                long_score += 8

            elif x["close"] < x["open"]:
                short_score += 8

        # ====================================================
        # VWAP
        # ====================================================

        if pd.notna(x["vwap"]):

            if price > x["vwap"]:
                long_score += 5

            elif price < x["vwap"]:
                short_score += 5

        # ====================================================
        # STRUCTURE
        # ====================================================

        if price > resistance:
            long_score += 10

        elif price < support:
            short_score += 10

        # ====================================================
        # FINAL DIRECTION
        # ====================================================

        if long_score > short_score:
            direction = "LONG"
            score = long_score

        elif short_score > long_score:
            direction = "SHORT"
            score = short_score

        else:
            direction = "NEUTRAL"
            score = max(
                long_score,
                short_score
            )

        # ----------------------------------------------------
        # Trend labels
        # ----------------------------------------------------

        trend_15m = (
            "BULLISH"
            if x["close"] > x["ema20"]
            else "BEARISH"
        )

        trend_1h = (
            "BULLISH"
            if h1["close"] > h1["ema20"]
            else "BEARISH"
        )

        trend_4h = (
            "BULLISH"
            if h4["close"] > h4["ema20"]
            else "BEARISH"
        )

        # ----------------------------------------------------
        # Multi-timeframe alignment
        # ----------------------------------------------------

        bullish_alignment = (
            trend_15m == "BULLISH" and
            trend_1h == "BULLISH" and
            trend_4h == "BULLISH"
        )

        bearish_alignment = (
            trend_15m == "BEARISH" and
            trend_1h == "BEARISH" and
            trend_4h == "BEARISH"
        )

        if bullish_alignment:
            timeframe_alignment = "FULL_BULLISH"

        elif bearish_alignment:
            timeframe_alignment = "FULL_BEARISH"

        else:
            timeframe_alignment = "MIXED"

        # ----------------------------------------------------
        # Setup classification
        # ----------------------------------------------------

        if (
            bullish_alignment and
            x["macd_histogram"] > 0 and
            x["volume_ratio"] >= 1.3
        ):
            setup = "TREND_CONTINUATION_LONG"

        elif (
            bearish_alignment and
            x["macd_histogram"] < 0 and
            x["volume_ratio"] >= 1.3
        ):
            setup = "TREND_CONTINUATION_SHORT"

        elif price > resistance:
            setup = "RESISTANCE_BREAKOUT"

        elif price < support:
            setup = "SUPPORT_BREAKDOWN"

        elif timeframe_alignment == "MIXED":
            setup = "MIXED_TIMEFRAME"

        else:
            setup = "STANDARD_SETUP"

        # ----------------------------------------------------
        # Return technical snapshot
        # ----------------------------------------------------

        return {
            "direction": direction,

            "score": min(
                float(score),
                100
            ),

            "long_score": float(long_score),

            "short_score": float(short_score),

            "price": price,

            "rsi": float(x["rsi"]),

            "atr": float(x["atr"]),

            "adx": float(x["adx"]),

            "ema20": float(x["ema20"]),

            "ema50": float(x["ema50"]),

            "ema200": float(x["ema200"]),

            "macd": float(x["macd"]),

            "macd_signal": float(
                x["macd_signal"]
            ),

            "macd_histogram": float(
                x["macd_histogram"]
            ),

            "volume_ratio": float(
                x["volume_ratio"]
            ),

            "vwap": float(x["vwap"])
            if pd.notna(x["vwap"])
            else None,

            "resistance": resistance,

            "support": support,

            "15m_trend": trend_15m,

            "1h_trend": trend_1h,

            "4h_trend": trend_4h,

            "timeframe_alignment":
                timeframe_alignment,

            "setup": setup
        }
