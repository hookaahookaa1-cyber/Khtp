from config import Config


class RiskEngine:

    @staticmethod
    def calculate(
        direction,
        entry,
        atr,
        capital,
        risk_pct,
        leverage,
        support=None,
        resistance=None
    ):
        # Basic validation
        if direction not in ("LONG", "SHORT"):
            return None

        if entry is None or entry <= 0:
            return None

        if atr is None or atr <= 0:
            return None

        if capital is None or capital <= 0:
            return None

        if risk_pct is None or risk_pct <= 0:
            return None

        if leverage is None or leverage <= 0:
            return None

        # Enforce configured maximum leverage
        leverage = min(
            float(leverage),
            float(Config.MAX_LEVERAGE)
        )

        # Maximum amount we are willing to lose
        risk_usd = float(capital) * float(risk_pct)

        # ATR-based stop distance
        stop_distance = float(atr) * 2.0

        if direction == "LONG":
            stop = float(entry) - stop_distance
            tp1 = float(entry) + (stop_distance * 2.0)
            tp2 = float(entry) + (stop_distance * 3.0)

        else:
            stop = float(entry) + stop_distance
            tp1 = float(entry) - (stop_distance * 2.0)
            tp2 = float(entry) - (stop_distance * 3.0)

        # Safety check
        if stop <= 0 or tp1 <= 0 or tp2 <= 0:
            return None

        risk_per_unit = abs(float(entry) - stop)

        if risk_per_unit <= 0:
            return None

        # Position quantity based on maximum allowed loss
        quantity = risk_usd / risk_per_unit

        if quantity <= 0:
            return None

        notional = quantity * float(entry)
        margin = notional / leverage

        # TP1 is 2R with the current stop model
        risk_reward = abs(tp1 - float(entry)) / risk_per_unit

        return {
            "direction": direction,
            "entry": float(entry),
            "stop": float(stop),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "risk_usd": float(risk_usd),
            "quantity": float(quantity),
            "notional": float(notional),
            "margin": float(margin),
            "leverage": float(leverage),
            "risk_reward": float(risk_reward),
            "support": support,
            "resistance": resistance
        }
