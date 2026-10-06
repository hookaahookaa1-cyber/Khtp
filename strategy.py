class Strategy:

    STRATEGY_ID = "TREND_CONTINUATION"
    STRATEGY_VERSION = "1.0"

    ENTRY_METHODS = {
        "BREAKOUT",
        "PULLBACK"
    }

    @classmethod
    def metadata(
        cls,
        entry_method="PULLBACK",
        market_regime="UNKNOWN",
        timeframe_profile="15m+1h+4h",
        entry_timeframe="5m"
    ):
        if entry_method not in cls.ENTRY_METHODS:
            entry_method = "PULLBACK"

        return {
            "strategy_id": cls.STRATEGY_ID,
            "strategy_version": cls.STRATEGY_VERSION,
            "entry_method": entry_method,
            "market_regime": market_regime,
            "timeframe_profile": timeframe_profile,
            "entry_timeframe": entry_timeframe
        }

    @classmethod
    def is_valid_direction(cls, direction):
        return direction in {
            "LONG",
            "SHORT"
        }

    @classmethod
    def is_valid_entry_method(cls, entry_method):
        return entry_method in cls.ENTRY_METHODS
