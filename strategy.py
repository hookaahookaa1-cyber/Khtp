
class Strategy:
    """
    Central strategy registry.

    Strategy identity and versioning stay separate from
    technical analysis and execution.
    """

    STRATEGIES = {
        "TREND_CONTINUATION": {
            "version": "1.0",
            "enabled": True,
            "description": "Multi-timeframe trend continuation.",
            "entry_methods": {
                "BREAKOUT",
                "PULLBACK"
            },
            "timeframe_profile": "15m+1h+4h",
            "entry_timeframe": "5m",
        },

        "BREAKOUT": {
            "version": "1.0",
            "enabled": True,
            "description": "Confirmed structural breakout with momentum.",
            "entry_methods": {
                "BREAKOUT"
            },
            "timeframe_profile": "15m+1h+4h",
            "entry_timeframe": "5m",
        },

        "PULLBACK": {
            "version": "1.0",
            "enabled": True,
            "description": "Trend continuation after a controlled pullback.",
            "entry_methods": {
                "PULLBACK"
            },
            "timeframe_profile": "15m+1h+4h",
            "entry_timeframe": "5m",
        },

        "MOMENTUM": {
            "version": "1.0",
            "enabled": False,
            "description": "Momentum continuation strategy.",
            "entry_methods": {
                "BREAKOUT"
            },
            "timeframe_profile": "15m+1h+4h",
            "entry_timeframe": "5m",
        },

        # BRR is registered separately and remains disabled
        # until its signal logic has been tested and integrated.
        "BRR": {
            "version": "0.1.0",
            "enabled": False,
            "description": (
                "Breakout, first retest, and rejection. "
                "Shadow-analysis mode only; no live execution."
            ),
            "entry_methods": {
                "BREAKOUT"
            },
            "timeframe_profile": "15m+1h",
            "entry_timeframe": "15m",
            "structure_timeframe": "1h",
            "execution_mode": "SHADOW",
        },
    }

    DEFAULT_STRATEGY = "TREND_CONTINUATION"

    @classmethod
    def get(cls, strategy_id):
        return cls.STRATEGIES.get(strategy_id)

    @classmethod
    def exists(cls, strategy_id):
        return strategy_id in cls.STRATEGIES

    @classmethod
    def is_enabled(cls, strategy_id):
        strategy = cls.get(strategy_id)

        if not strategy:
            return False

        return bool(strategy.get("enabled", False))

    @classmethod
    def version(cls, strategy_id):
        strategy = cls.get(strategy_id)

        if not strategy:
            return None

        return strategy.get("version")

    @classmethod
    def all(cls):
        return {
            strategy_id: data.copy()
            for strategy_id, data in cls.STRATEGIES.items()
        }

    @classmethod
    def enabled(cls):
        return {
            strategy_id: data.copy()
            for strategy_id, data in cls.STRATEGIES.items()
            if data.get("enabled", False)
        }

    @classmethod
    def metadata(
        cls,
        strategy_id=None,
        entry_method="PULLBACK",
        market_regime="UNKNOWN",
        timeframe_profile=None,
        entry_timeframe=None
    ):
        strategy_id = strategy_id or cls.DEFAULT_STRATEGY

        if not cls.exists(strategy_id):
            strategy_id = cls.DEFAULT_STRATEGY

        strategy = cls.get(strategy_id)

        allowed_methods = strategy.get(
            "entry_methods",
            {"PULLBACK"}
        )

        if entry_method not in allowed_methods:
            entry_method = sorted(allowed_methods)[0]

        if timeframe_profile is None:
            timeframe_profile = strategy.get(
                "timeframe_profile",
                "15m+1h+4h"
            )

        if entry_timeframe is None:
            entry_timeframe = strategy.get(
                "entry_timeframe",
                "5m"
            )

        metadata = {
            "strategy_id": strategy_id,
            "strategy_version": strategy.get(
                "version",
                "1.0"
            ),
            "entry_method": entry_method,
            "market_regime": market_regime,
            "timeframe_profile": timeframe_profile,
            "entry_timeframe": entry_timeframe,
        }

        if strategy_id == "BRR":
            metadata["structure_timeframe"] = strategy.get(
                "structure_timeframe",
                "1h"
            )
            metadata["execution_mode"] = strategy.get(
                "execution_mode",
                "SHADOW"
            )

        return metadata

    @classmethod
    def is_valid_direction(cls, direction):
        return direction in {
            "LONG",
            "SHORT"
        }

    @classmethod
    def is_valid_entry_method(cls, entry_method):
        return entry_method in {
            "BREAKOUT",
            "PULLBACK"
        }

    @classmethod
    def supports_entry_method(
        cls,
        strategy_id,
        entry_method
    ):
        strategy = cls.get(strategy_id)

        if not strategy:
            return False

        return entry_method in strategy.get(
            "entry_methods",
            set()
        )
