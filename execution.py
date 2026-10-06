import logging

import ccxt

from config import Config


class ExecutionEngine:
    """
    Bitget execution layer.

    Current stage:
    - Selects DEMO or LIVE credentials.
    - Validates environment and trading parameters.
    - Prepares order information.
    - Does NOT submit live/demo orders yet.
    """

    def __init__(self):
        self.environment = Config.TRADING_ENV

        if self.environment not in ("DEMO", "LIVE"):
            raise ValueError(
                "TRADING_ENV must be DEMO or LIVE"
            )

        if self.environment == "DEMO":
            self.api_key = Config.BITGET_DEMO_API_KEY
            self.secret = Config.BITGET_DEMO_SECRET
            self.password = Config.BITGET_DEMO_PASSWORD
        else:
            self.api_key = Config.BITGET_LIVE_API_KEY
            self.secret = Config.BITGET_LIVE_SECRET
            self.password = Config.BITGET_LIVE_PASSWORD

        self.exchange = None

        self._initialize_exchange()

    def _initialize_exchange(self):
        if not self.api_key:
            logging.warning(
                f"Bitget {self.environment} API key is not configured."
            )
            return

        if not self.secret:
            logging.warning(
                f"Bitget {self.environment} secret is not configured."
            )
            return

        if not self.password:
            logging.warning(
                f"Bitget {self.environment} password is not configured."
            )
            return

        try:
            options = {
                "defaultType": "swap"
            }

            self.exchange = ccxt.bitget({
                "apiKey": self.api_key,
                "secret": self.secret,
                "password": self.password,
                "enableRateLimit": True,
                "options": options
            })

            if self.environment == "DEMO":
                self.exchange.enable_demo_trading(True)

            self.exchange.load_markets()

            logging.info(
                f"Bitget {self.environment} execution "
                "environment initialized."
            )

        except Exception as e:
            self.exchange = None
            logging.error(
                f"Bitget initialization error: {e}"
            )

    def is_ready(self):
        return self.exchange is not None

    def fetch_equity(self):
        if not self.is_ready():
            return None

        try:
            balance = self.exchange.fetch_balance()

            usdt = balance.get("USDT", {})

            total = usdt.get("total")

            if total is None:
                total = usdt.get("free")

            if total is None:
                logging.warning(
                    "USDT equity could not be determined."
                )
                return None

            equity = float(total)

            if equity <= 0:
                logging.warning(
                    f"Invalid USDT equity: {equity}"
                )
                return None

            return equity

        except Exception as e:
            logging.error(
                f"Equity fetch error: {e}"
            )
            return None

    def market_info(self, symbol):
        if not self.is_ready():
            return None

        try:
            market = self.exchange.market(symbol)

            return {
                "symbol": symbol,
                "contract": market.get("contract", False),
                "contract_size": market.get(
                    "contractSize"
                ),
                "amount_min": market.get(
                    "limits", {}
                ).get("amount", {}).get("min"),
                "amount_max": market.get(
                    "limits", {}
                ).get("amount", {}).get("max"),
                "price_min": market.get(
                    "limits", {}
                ).get("price", {}).get("min"),
                "precision_amount": market.get(
                    "precision", {}
                ).get("amount"),
                "precision_price": market.get(
                    "precision", {}
                ).get("price")
            }

        except Exception as e:
            logging.error(
                f"Market info error {symbol}: {e}"
            )
            return None

    def normalize_quantity(self, symbol, quantity):
        if not self.is_ready():
            return None

        try:
            quantity = float(quantity)

            if quantity <= 0:
                return None

            logging.info(
                f"Execution market check: requested={symbol}"
            )

            logging.info(
                f"Execution symbol exists="
                f"{symbol in self.exchange.markets}"
            )

            formatted = self.exchange.amount_to_precision(
                symbol,
                quantity
            )

            normalized = float(formatted)

            market = self.exchange.market(symbol)

            minimum = (
                market.get("limits", {})
                .get("amount", {})
                .get("min")
            )

            if minimum is not None:
                if normalized < float(minimum):
                    logging.warning(
                        f"Quantity below exchange minimum: "
                        f"{symbol} quantity={normalized} "
                        f"minimum={minimum}"
                    )
                    return None

            return normalized

        except Exception as e:
            logging.error(
                f"Quantity normalization error "
                f"{symbol}: {e}"
            )
            return None

    def validate_order(
        self,
        symbol,
        direction,
        quantity,
        leverage,
        entry,
        stop,
        tp1,
        tp2
    ):
        if direction not in ("LONG", "SHORT"):
            return False, "Invalid direction."

        if not self.is_ready():
            return False, (
                f"Bitget {self.environment} "
                "execution is not ready."
            )

        if leverage <= 0:
            return False, "Invalid leverage."

        if leverage > Config.MAX_LEVERAGE:
            return False, "Leverage exceeds configured maximum."

        if entry <= 0:
            return False, "Invalid entry price."

        if stop <= 0 or tp1 <= 0 or tp2 <= 0:
            return False, "Invalid SL/TP price."

        if direction == "LONG":
            if stop >= entry:
                return False, "LONG stop must be below entry."

            if tp1 <= entry or tp2 <= entry:
                return False, "LONG TP must be above entry."

        elif direction == "SHORT":
            if stop <= entry:
                return False, "SHORT stop must be above entry."

            if tp1 >= entry or tp2 >= entry:
                return False, "SHORT TP must be below entry."

        normalized_quantity = self.normalize_quantity(
            symbol,
            quantity
        )

        if normalized_quantity is None:
            return False, (
                "Quantity is below exchange minimum "
                "or could not be normalized."
            )

        return True, "Order validation passed."

    def prepare_order(
        self,
        symbol,
        direction,
        quantity,
        leverage,
        entry,
        stop,
        tp1,
        tp2
    ):
        valid, message = self.validate_order(
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            leverage=leverage,
            entry=entry,
            stop=stop,
            tp1=tp1,
            tp2=tp2
        )

        if not valid:
            return {
                "ready": False,
                "environment": self.environment,
                "error": message
            }

        normalized_quantity = self.normalize_quantity(
            symbol,
            quantity
        )

        if normalized_quantity is None:
            return {
                "ready": False,
                "environment": self.environment,
                "error": (
                    "Quantity normalization failed."
                )
            }

        side = (
            "buy"
            if direction == "LONG"
            else "sell"
        )

        close_side = (
            "sell"
            if direction == "LONG"
            else "buy"
        )

        return {
            "ready": True,
            "environment": self.environment,
            "symbol": symbol,
            "direction": direction,
            "side": side,
            "close_side": close_side,
            "quantity": normalized_quantity,
            "leverage": float(leverage),
            "entry": float(entry),
            "stop": float(stop),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "margin_mode": "isolated",
            "execution_enabled": False
        }

    def execute(self, order_plan, mode="MANUAL"):
        if mode != "AUTO":
            return {
                "success": False,
                "executed": False,
                "environment": self.environment,
                "error": (
                    "Automatic execution is blocked "
                    "because the bot is not in AUTO mode."
                )
            }

        if not order_plan:
            return {
                "success": False,
                "executed": False,
                "environment": self.environment,
                "error": "Empty order plan."
            }

        return {
            "success": False,
            "executed": False,
            "environment": self.environment,
            "error": (
                "Order execution is disabled during "
                "the initial validation stage."
            )
        }
