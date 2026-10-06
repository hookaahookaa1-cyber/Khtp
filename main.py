
import os
import json
import time
import math
import sqlite3
import logging
import threading
from datetime import datetime, date, timedelta

import requests
import numpy as np
import pandas as pd
import ccxt

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from config import Config
from database.database import Database
from telegram.bot import Telegram
from telegram.ui import TelegramUI
from market import Market
from indicators import Indicators
from structure import Structure
from strategy import Strategy
from technical_engine import TechnicalEngine
from risk_engine import RiskEngine
from execution import ExecutionEngine
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# INDICATORS
# ============================================================

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

        rs = avg_gain / avg_loss.replace(0, np.nan)

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
        fast = Indicators.ema(series, 12)
        slow = Indicators.ema(series, 26)

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
            tr.replace(0, np.nan)
        )

        minus_di = (
            100 *
            minus_dm.ewm(
                alpha=1 / period,
                adjust=False
            ).mean() /
            tr.replace(0, np.nan)
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
            volume_ma.replace(0, np.nan)
        )

    @staticmethod
    def enrich(df):
        df = df.copy()

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Momentum
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Volatility
        # ----------------------------------------------------

        df["atr"] = Indicators.atr(df)

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        df["volume_ma"] = (
            df["volume"]
            .rolling(20)
            .mean()
        )

        df["volume_ratio"] = (
            Indicators.volume_ratio(df)
        )

        # ----------------------------------------------------
        # VWAP
        # ----------------------------------------------------

        df["vwap"] = Indicators.vwap(df)

        return df

# ============================================================
# MARKET STRUCTURE
# ============================================================

class Structure:

    @staticmethod
    def levels(df, window=7):
        if df is None or df.empty:
            return {
                "resistance": None,
                "support": None
            }

        if len(df) < (window * 2 + 1):
            return {
                "resistance": float(
                    df["high"].tail(20).max()
                ),
                "support": float(
                    df["low"].tail(20).min()
                )
            }

        highs = df["high"]
        lows = df["low"]

        resistance = highs[
            highs ==
            highs.rolling(
                window * 2 + 1,
                center=True
            ).max()
        ]

        support = lows[
            lows ==
            lows.rolling(
                window * 2 + 1,
                center=True
            ).min()
        ]

        resistance = (
            resistance
            .dropna()
            .tail(10)
            .tolist()
        )

        support = (
            support
            .dropna()
            .tail(10)
            .tolist()
        )

        return {
            "resistance": (
                resistance[-1]
                if resistance
                else float(
                    df["high"].tail(20).max()
                )
            ),

            "support": (
                support[-1]
                if support
                else float(
                    df["low"].tail(20).min()
                )
            )
        }


class AIAnalysis(BaseModel):
    direction: str = Field(description="LONG, SHORT, or NEUTRAL")
    decision: str = Field(description="TAKE, CONSIDER, or IGNORE")
    confidence: float
    setup: str
    regime: str
    risk_flags: list[str]
    reason: str


class AIEngine:
    SYSTEM_PROMPT = """
You are a conservative futures market analysis assistant.

You DO NOT execute trades.
You DO NOT calculate position size.
You DO NOT choose leverage.
You DO NOT override the risk engine.

Your job is to review an already filtered technical setup.

Possible directions:
LONG, SHORT, NEUTRAL

Possible decisions:
TAKE, CONSIDER, IGNORE

Rules:
1. Never invent market data, prices, or indicators.
2. Do not calculate position size.
3. Do not choose leverage.
4. Do not override risk controls.
5. Consider 10m, 1h, and 4h alignment.
6. Consider BTC context.
7. Penalize conflicting higher-timeframe trends.
8. Penalize weak volume.
9. Penalize extreme RSI conditions.
10. If evidence is mixed or uncertain, prefer CONSIDER or IGNORE.
11. Be conservative.
12. Return ONLY the requested JSON schema.
"""

    def __init__(self):
        self.client = None

        if Config.GEMINI_API_KEY:
            try:
                self.client = genai.Client(
                    api_key=Config.GEMINI_API_KEY
                )
                logging.info("Gemini AI initialized successfully.")
            except Exception as e:
                logging.error(f"Gemini initialization error: {e}")

    def analyze(self, snapshot):
        if not self.client:
            return {
                "direction": "NEUTRAL",
                "decision": "IGNORE",
                "confidence": 0,
                "setup": "UNKNOWN",
                "regime": "UNKNOWN",
                "risk_flags": ["AI_UNAVAILABLE"],
                "reason": "Gemini AI is not available."
            }

        try:
            return self.gemini(snapshot)

        except Exception as e:
            logging.error(f"Gemini error: {e}")

            return {
                "direction": "NEUTRAL",
                "decision": "IGNORE",
                "confidence": 0,
                "setup": "UNKNOWN",
                "regime": "UNKNOWN",
                "risk_flags": ["AI_ERROR"],
                "reason": "Gemini analysis failed safely."
            }

    def gemini(self, snapshot):
        prompt = (
            self.SYSTEM_PROMPT
            + "\n\nMARKET SNAPSHOT:\n"
            + json.dumps(
                snapshot,
                ensure_ascii=False,
                indent=2,
                default=str
            )
        )

        response = self.client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIAnalysis
            )
        )

        result = AIAnalysis.model_validate_json(response.text)

        return result.model_dump()

class TradingBot:

    def __init__(self):
        self.config = Config()
        self.ai = AIEngine()
        self.execution = ExecutionEngine()

        self.db = Database(
            self.config.DB_FILE,
            initial_capital=self.config.CAPITAL
        )

        self.telegram = Telegram()
        self.market = Market()

        # AUTO is the default mode.
        # AUTO = automatic execution enabled.
        # MANUAL = signals only, no automatic execution.
        self.mode = "AUTO"

        self.last_signal = {}
        self.running = True

    def set_mode(self, mode):
        mode = str(mode).upper()

        if mode not in ("AUTO", "MANUAL"):
            return False

        self.mode = mode

        logging.info(
            f"Trading mode changed to {self.mode}"
        )

        self.telegram.send_mode_panel(
            self.mode
        )

        return True

    def get_exchange_equity(self):
        equity = self.execution.fetch_equity()

        if equity is None:
            logging.warning(
                "Exchange equity is unavailable."
            )
            return None

        logging.info(
            f"Bitget {self.execution.environment} "
            f"USDT equity: ${equity:.2f}"
        )

        return equity

    def btc_context(self):
        try:
            df1 = self.market.fetch(
                self.config.BTC_SYMBOL,
                "1h",
                100
            )

            df4 = self.market.fetch(
                self.config.BTC_SYMBOL,
                "4h",
                100
            )

            if df1 is None or df4 is None:
                return {}

            a1 = Indicators.enrich(df1)
            a4 = Indicators.enrich(df4)

            if len(a1) < 2 or len(a4) < 2:
                return {}

            c1 = a1.iloc[-2]
            c4 = a4.iloc[-2]

            return {
                "btc_1h": (
                    "BULLISH"
                    if c1["close"] > c1["ema20"]
                    else "BEARISH"
                ),
                "btc_4h": (
                    "BULLISH"
                    if c4["close"] > c4["ema20"]
                    else "BEARISH"
                ),
                "btc_rsi_1h": float(c1["rsi"])
            }

        except Exception as e:
            logging.error(
                f"BTC context error: {e}"
            )
            return {}

    def snapshot(self, symbol, tech, btc):
        return {
            "symbol": symbol,
            "market": "BITGET_USDT_M_PERPETUAL",
            "margin_mode": "ISOLATED",
            "direction_candidate": tech["direction"],
            "technical_score": tech["score"],
            "price": tech["price"],

            "10m": {
                "rsi": tech["rsi"],
                "atr": tech["atr"],
                "adx": tech["adx"],
                "ema20": tech["ema20"],
                "ema50": tech["ema50"],
                "ema200": tech["ema200"],
                "macd": tech["macd"],
                "macd_signal": tech["macd_signal"],
                "macd_histogram": tech["macd_histogram"],
                "volume_ratio": tech["volume_ratio"],
                "vwap": tech["vwap"]
            },

            "1h": {
                "trend": tech["1h_trend"]
            },

            "4h": {
                "trend": tech["4h_trend"]
            },

            "structure": {
                "support": tech["support"],
                "resistance": tech["resistance"]
            },

            "timeframe_alignment": tech["timeframe_alignment"],
            "setup": tech["setup"],
            "btc_context": btc
        }

    def btc_warning(self, direction, btc):
        if not btc:
            return []

        flags = []

        if (
            direction == "LONG"
            and btc.get("btc_1h") == "BEARISH"
        ):
            flags.append("BTC_1H_AGAINST_LONG")

        if (
            direction == "SHORT"
            and btc.get("btc_1h") == "BULLISH"
        ):
            flags.append("BTC_1H_AGAINST_SHORT")

        if (
            direction == "LONG"
            and btc.get("btc_4h") == "BEARISH"
        ):
            flags.append("BTC_4H_AGAINST_LONG")

        if (
            direction == "SHORT"
            and btc.get("btc_4h") == "BULLISH"
        ):
            flags.append("BTC_4H_AGAINST_SHORT")

        return flags

    def evaluate(self, symbol):
        df15 = self.market.fetch(
            symbol,
            self.config.TF_MAIN
        )

        df1 = self.market.fetch(
            symbol,
            self.config.TF_1H
        )

        df4 = self.market.fetch(
            symbol,
            self.config.TF_4H
        )

        if (
            df15 is None
            or df1 is None
            or df4 is None
        ):
            return

        tech = TechnicalEngine.analyze(
            df15,
            df1,
            df4
        )

        if not tech:
            return

        if tech["direction"] == "NEUTRAL":
            return

        if tech["score"] < self.config.MIN_TECH_SCORE:
            return

        btc = self.btc_context()

        snapshot = self.snapshot(
            symbol,
            tech,
            btc
        )

        ai = self.ai.analyze(snapshot)

        if not ai:
            return

        if ai["direction"] != tech["direction"]:
            return

        if ai["confidence"] < self.config.MIN_AI_CONFIDENCE:
            return

        # In AUTO mode, only TAKE decisions can proceed
        # toward automatic execution.
        if (
            self.mode == "AUTO"
            and ai["decision"] != "TAKE"
        ):
            return

        # In MANUAL mode, IGNORE is still rejected.
        if (
            self.mode == "MANUAL"
            and ai["decision"] == "IGNORE"
        ):
            return

        flags = self.btc_warning(
            tech["direction"],
            btc
        )

        leverage = min(
            self.config.DEFAULT_LEVERAGE,
            self.config.MAX_LEVERAGE
        )

        exchange_equity = self.get_exchange_equity()

        capital = (
            exchange_equity
            if exchange_equity is not None
            else self.config.CAPITAL
        )

        risk = RiskEngine.calculate(
            direction=tech["direction"],
            entry=tech["price"],
            atr=tech["atr"],
            capital=capital,
            risk_pct=self.config.RISK_PER_TRADE,
            leverage=leverage,
            support=tech["support"],
            resistance=tech["resistance"]
        )

        if not risk:
            return

        # ====================================================
        # RISK GUARDS
        # ====================================================

        open_trades = self.db.get_open_trades()

        if len(open_trades) >= self.config.MAX_OPEN_PLANS:
            logging.warning(
                f"Max open trades reached: "
                f"{len(open_trades)}/"
                f"{self.config.MAX_OPEN_PLANS}"
            )
            return

        daily = self.db.get_daily_pnl()

        daily_loss_limit = (
            self.config.CAPITAL
            * self.config.MAX_DAILY_LOSS
        )

        if daily["pnl"] <= -daily_loss_limit:
            logging.warning(
                f"Daily loss limit reached: "
                f"${daily['pnl']:.2f}"
            )
            return

        order_plan = self.execution.prepare_order(
            symbol=symbol,
            direction=tech["direction"],
            quantity=risk["quantity"],
            leverage=leverage,
            entry=risk["entry"],
            stop=risk["stop"],
            tp1=risk["tp1"],
            tp2=risk["tp2"]
        )

        if not order_plan.get("ready"):
            logging.warning(
                f"Execution validation failed for "
                f"{symbol}: "
                f"{order_plan.get('error')}"
            )
            return

        key = (
            symbol,
            tech["direction"]
        )

        now = time.time()

        if (
            key in self.last_signal
            and now - self.last_signal[key] < 30 * 60
        ):
            return

        self.last_signal[key] = now

        all_flags = (
            flags
            + ai.get("risk_flags", [])
        )

        signal = {
            "symbol": symbol,
            "direction": tech["direction"],
            "price": tech["price"],
            "tech_score": tech["score"],
            "ai_confidence": ai["confidence"],
            "ai_decision": ai["decision"],
            "setup": ai["setup"],
            "regime": ai["regime"],
            "entry": risk["entry"],
            "stop": risk["stop"],
            "tp1": risk["tp1"],
            "tp2": risk["tp2"],
            "risk_reward": risk["risk_reward"],
            "ai_reason": ai["reason"],
            "execution_environment": order_plan["environment"],
            "execution_ready": order_plan["ready"],
            "execution_quantity": order_plan["quantity"],
            "risk_flags": all_flags
        }

        signal_id = self.db.save_signal(signal)

        emoji = (
            "🟢"
            if tech["direction"] == "LONG"
            else "🔴"
        )

        message = (
            f"{emoji} FUTURES SETUP\n"
            f"{symbol}\n\n"
            f"Mode: {self.mode}\n"
            f"Direction: {tech['direction']}\n\n"
            f"Entry: {risk['entry']:.6f}\n"
            f"Stop: {risk['stop']:.6f}\n"
            f"TP1: {risk['tp1']:.6f}\n"
            f"TP2: {risk['tp2']:.6f}\n\n"
            f"Risk: ${risk['risk_usd']:.2f}\n"
            f"Notional: ${risk['notional']:.2f}\n"
            f"Margin @ {leverage}x: ${risk['margin']:.2f}\n"
            f"R:R: 1:{risk['risk_reward']:.2f}\n\n"
            f"Technical Score: "
            f"{tech['score']:.0f}/100\n"
            f"AI Confidence: "
            f"{ai['confidence']:.0f}/100\n\n"
            f"Setup: {ai['setup']}\n"
            f"Regime: {ai['regime']}\n"
            f"BTC 1H: "
            f"{btc.get('btc_1h', 'N/A')}\n"
            f"BTC 4H: "
            f"{btc.get('btc_4h', 'N/A')}\n\n"
            f"AI: {ai['reason']}"
        )

        if all_flags:
            message += (
                "\n\n⚠️ Risk Flags:\n"
                + "\n".join(
                    f"• {x}"
                    for x in all_flags
                )
            )

        if self.mode == "AUTO":
            execution_result = self.execution.execute(
                order_plan,
                mode=self.mode
            )

            message += (
                "\n\n🤖 AUTO MODE\n"
                "Signal passed technical, AI and risk filters.\n"
                f"Execution: "
                f"{execution_result.get('error', 'N/A')}"
            )

        else:
            message += (
                "\n\n🖐 MANUAL MODE\n"
                "No automatic order will be sent."
            )

        keyboard = [
            [
                {
                    "text": "🟢 AUTO",
                    "callback_data": "mode_auto"
                },
                {
                    "text": "🔴 MANUAL",
                    "callback_data": "mode_manual"
                }
            ]
        ]

        self.telegram.send(
            message,
            keyboard
        )

        logging.info(
            f"SIGNAL {symbol} "
            f"{tech['direction']} "
            f"score={tech['score']} "
            f"mode={self.mode}"
        )
    def process_updates(self):
        updates = self.telegram.poll()

        for update in updates:
            try:
                if "callback_query" in update:
                    callback = update["callback_query"]
                    data = callback.get("data", "")

                    self.telegram.answer_callback(
                        callback.get("id", "")
                    )

                    if data == "mode_auto":
                        self.set_mode("AUTO")

                    elif data == "mode_manual":
                        self.set_mode("MANUAL")

                    continue

                if "message" not in update:
                    continue

                text = (
                    update["message"]
                    .get("text", "")
                    .strip()
                )

                if not text:
                    continue

                if text == "/auto":
                    self.set_mode("AUTO")

                elif text == "/manual":
                    self.set_mode("MANUAL")

                elif text == "/mode":
                    self.telegram.send_mode_panel(
                        self.mode
                    )

                elif text == "/status":
                    trades = self.db.get_open_trades()

                    msg = TelegramUI.status_message(
                        self.mode,
                        len(self.config.SYMBOLS),
                        len(trades)
                    )

                    self.telegram.send(msg)

                elif text == "/equity":
                    equity = self.get_exchange_equity()

                    if equity is None:
                        self.telegram.send(
                            "⚠️ Unable to read "
                            "Bitget USDT equity."
                        )
                    else:
                        self.telegram.send(
                            TelegramUI.equity_message(
                                self.execution.environment,
                                equity
                            )
                        )

                elif text == "/stats":
                    stats = self.db.stats()

                    self.telegram.send(
                        TelegramUI.stats_message(stats)
                    )

                elif text == "/open":
                    self.telegram.send(
                        TelegramUI.manual_open_message()
                    )

                elif text.startswith("/open "):
                    self.telegram.send(
                        TelegramUI.manual_order_disabled_message()
                    )

                elif text.startswith("/close "):
                    parts = text.split()

                    if len(parts) != 3:
                        self.telegram.send(
                            TelegramUI.close_usage_message()
                        )
                        continue

                    try:
                        trade_id = int(parts[1])
                        exit_price = float(parts[2])

                        result = self.db.close_trade(
                            trade_id,
                            exit_price
                        )

                        if not result:
                            self.telegram.send(
                                TelegramUI.trade_not_found_message()
                            )
                            continue

                        self.telegram.send(
                            TelegramUI.trade_closed_message(
                                result
                            )
                        )

                    except Exception as e:
                        logging.error(
                            f"Close command error: {e}"
                        )

                        self.telegram.send(
                            TelegramUI.invalid_close_message()
                        )

            except Exception as e:
                logging.error(
                    f"Update processing error: {e}"
                )

    def run(self):
        self.telegram.send(
            "🤖 AI Futures Trading Bot Started\n\n"
            "Market: Bitget USDT-M Perpetual\n"
            "Margin: Isolated\n"
            "Modes: LONG + SHORT\n"
            "Default Mode: AUTO\n"
            "AI: Gemini\n"
            "Risk Engine: Enabled\n\n"
            "⚠️ Execution layer is being initialized."
        )

        self.telegram.send_mode_panel(
            self.mode
        )

        while self.running:
            try:
                self.process_updates()

                for symbol in self.config.SYMBOLS:
                    try:
                        self.evaluate(symbol)
                    except Exception as e:
                        logging.error(
                            f"Evaluation error "
                            f"{symbol}: {e}"
                        )

                    time.sleep(2)

                time.sleep(
                    self.config.SCAN_SECONDS
                )

            except KeyboardInterrupt:
                self.running = False
                break

            except Exception as e:
                logging.error(
                    f"Main loop error: {e}"
                )
                time.sleep(10)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
