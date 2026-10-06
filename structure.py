import pandas as pd


class Structure:

    @staticmethod
    def levels(df, window=7):
        if df is None or df.empty:
            return {
                "support": None,
                "resistance": None
            }

        try:
            highs = df["high"]
            lows = df["low"]

            resistance = (
                highs.rolling(window)
                .max()
                .iloc[-1]
            )

            support = (
                lows.rolling(window)
                .min()
                .iloc[-1]
            )

            if pd.isna(support):
                support = None

            if pd.isna(resistance):
                resistance = None

            return {
                "support": (
                    float(support)
                    if support is not None
                    else None
                ),
                "resistance": (
                    float(resistance)
                    if resistance is not None
                    else None
                )
            }

        except Exception:
            return {
                "support": None,
                "resistance": None
          }
