import os


class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite"
    )

    TRADING_ENV = os.getenv(
        "TRADING_ENV",
        "DEMO"
    ).upper()

    BITGET_LIVE_API_KEY = os.getenv(
        "BITGET_LIVE_API_KEY",
        ""
    )
    BITGET_LIVE_SECRET = os.getenv(
        "BITGET_LIVE_SECRET",
        ""
    )
    BITGET_LIVE_PASSWORD = os.getenv(
        "BITGET_LIVE_PASSWORD",
        ""
    )

    BITGET_DEMO_API_KEY = os.getenv(
        "BITGET_DEMO_API_KEY",
        ""
    )
    BITGET_DEMO_SECRET = os.getenv(
        "BITGET_DEMO_SECRET",
        ""
    )
    BITGET_DEMO_PASSWORD = os.getenv(
        "BITGET_DEMO_PASSWORD",
        ""
    )

    SYMBOLS = [
        "FET/USDT:USDT",
        "NEAR/USDT:USDT",
        "RENDER/USDT:USDT",
    ]

    BTC_SYMBOL = "BTC/USDT:USDT"

    TF_MAIN = "15m"
    TF_1H = "1h"
    TF_4H = "4h"
    TF_ENTRY = "5m"

    CAPITAL = float(
        os.getenv("CAPITAL", "1000")
    )

    RISK_PER_TRADE = float(
        os.getenv("RISK_PER_TRADE", "0.01")
    )

    MAX_DAILY_LOSS = float(
        os.getenv("MAX_DAILY_LOSS", "0.03")
    )

    MAX_OPEN_PLANS = int(
        os.getenv("MAX_OPEN_PLANS", "3")
    )

    DEFAULT_LEVERAGE = int(
        os.getenv("DEFAULT_LEVERAGE", "10")
    )

    MAX_LEVERAGE = int(
        os.getenv("MAX_LEVERAGE", "20")
    )

    MIN_TECH_SCORE = float(
        os.getenv("MIN_TECH_SCORE", "65")
    )

    MIN_AI_CONFIDENCE = float(
        os.getenv("MIN_AI_CONFIDENCE", "65")
    )

    SCAN_SECONDS = int(
        os.getenv("SCAN_SECONDS", "60")
    )

    DB_FILE = "data/bot.db"
