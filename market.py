import logging

import ccxt
import pandas as pd


class Market:

    def __init__(self):
        self.exchange = ccxt.bitget({
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap"
            }
        })

        try:
            self.exchange.load_markets()
            logging.info("Bitget markets loaded successfully.")

        except Exception as e:
            logging.error(
                f"Failed to load Bitget markets: {e}"
            )
            raise

    # ========================================================
    # OHLCV DATA
    # ========================================================

    def fetch(self, symbol, timeframe, limit=250):
        try:
            if symbol not in self.exchange.markets:
                logging.error(
                    f"Symbol not found on Bitget: {symbol}"
                )
                return None

            candles = self.exchange.fetch_ohlcv(
                symbol,
                timeframe,
                limit=limit
            )

            if not candles:
                return None

            df = pd.DataFrame(
                candles,
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume"
                ]
            )

            for col in [
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                unit="ms",
                utc=True
            )

            df = df.dropna(
                subset=[
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume"
                ]
            )

            df = df.sort_values(
                "timestamp"
            ).reset_index(drop=True)

            return df

        except Exception as e:
            logging.error(
                f"Market error {symbol} {timeframe}: {e}"
            )
            return None

    # ========================================================
    # CURRENT PRICE
    # ========================================================

    def price(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(
                symbol
            )

            last = ticker.get("last")

            if last is None:
                return None

            return float(last)

        except Exception as e:
            logging.error(
                f"Price error {symbol}: {e}"
            )
            return None

    # ========================================================
    # TICKER
    # ========================================================

    def ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(
                symbol
            )

        except Exception as e:
            logging.error(
                f"Ticker error {symbol}: {e}"
            )
            return None

    # ========================================================
    # MARKET INFO
    # ========================================================

    def market_info(self, symbol):
        try:
            return self.exchange.market(
                symbol
            )

        except Exception as e:
            logging.error(
                f"Market info error {symbol}: {e}"
            )
            return None

    # ========================================================
    # LAST CANDLE
    # ========================================================

    def last_candle(self, symbol, timeframe):
        df = self.fetch(
            symbol,
            timeframe,
            limit=5
        )

        if df is None or df.empty:
            return None

        return df.iloc[-1].to_dict()
