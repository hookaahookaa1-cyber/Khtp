import numpy as np
import pandas as pd


class Indicators:

    @staticmethod
    def ema(series, period):
        return series.ewm(
            span=period,
            adjust=False
        ).mean()

    @staticmethod
    def rsi(series, period=14):
        delta = series.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(
            alpha=1 / period,
            adjust=False
        ).mean()

        avg_loss = loss.ewm(
            alpha=1 / period,
            adjust=False
        ).mean()

        rs = avg_gain / avg_loss.replace(
            0,
            np.nan
        )

        return 100 - (
            100 / (1 + rs)
        )

    @staticmethod
    def atr(df, period=14):
        high_low = (
            df["high"] -
            df["low"]
        )

        high_close = (
            df["high"] -
            df["close"].shift()
        ).abs()

        low_close = (
            df["low"] -
            df["close"].shift()
        ).abs()

        tr = pd.concat(
            [
                high_low,
                high_close,
                low_close
            ],
            axis=1
        ).max(axis=1)

        return tr.ewm(
            alpha=1 / period,
            adjust=False
        ).mean()

    @staticmethod
    def macd(series):
        fast = Indicators.ema(
            series,
            12
        )

        slow = Indicators.ema(
            series,
            26
        )

        macd = fast - slow

        signal = Indicators.ema(
            macd,
            9
        )

        histogram = macd - signal

        return macd, signal, histogram

    @staticmethod
    def adx(df, period=14):
        high = df["high"]
        low = df["low"]

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where(
            (plus_dm > minus_dm) &
            (plus_dm > 0),
            0
        )

        minus_dm = minus_dm.where(
            (minus_dm > plus_dm) &
            (minus_dm > 0),
            0
        )

        tr = Indicators.atr(
            df,
            period
        )

        plus_di = (
            100 *
            plus_dm.ewm(
                alpha=1 / period,
                adjust=False
            ).mean() /
            tr.replace(
                0,
                np.nan
            )
        )

        minus_di = (
            100 *
            minus_dm.ewm(
                alpha=1 / period,
                adjust=False
            ).mean() /
            tr.replace(
                0,
                np.nan
            )
        )

        dx = (
            (plus_di - minus_di).abs() /
            (plus_di + minus_di).replace(
                0,
                np.nan
            )
        ) * 100

        return dx.ewm(
            alpha=1 / period,
            adjust=False
        ).mean()

    @staticmethod
    def vwap(df):
        typical_price = (
            df["high"] +
            df["low"] +
            df["close"]
        ) / 3

        volume = df["volume"]

        cumulative_volume = volume.cumsum()

        return (
            typical_price * volume
        ).cumsum() / cumulative_volume.replace(
            0,
            np.nan
        )

    @staticmethod
    def volume_ratio(df, period=20):
        volume_ma = (
            df["volume"]
            .rolling(period)
            .mean()
        )

        return (
            df["volume"] /
            volume_ma.replace(
                0,
                np.nan
            )
        )

    @staticmethod
    def enrich(df):
        df = df.copy()

        df["ema20"] = Indicators.ema(
            df["close"],
            20
        )

        df["ema50"] = Indicators.ema(
            df["close"],
            50
        )

        df["ema200"] = Indicators.ema(
            df["close"],
            200
        )

        df["rsi"] = Indicators.rsi(
            df["close"]
        )

        (
            df["macd"],
            df["macd_signal"],
            df["macd_histogram"]
        ) = Indicators.macd(
            df["close"]
        )

        df["adx"] = Indicators.adx(df)

        df["atr"] = Indicators.atr(df)

        df["volume_ma"] = (
            df["volume"]
            .rolling(20)
            .mean()
        )

        df["volume_ratio"] = (
            Indicators.volume_ratio(df)
        )

        df["vwap"] = Indicators.vwap(df)

        return df
