import logging
import ccxt
from config import Config


class ExecutionEngine:
    """
    Bitget execution layer.

    Current stage:
    - Selects DEMO or LIVE credentials.
    - Validates environment and trading parameters.
    - Loads Bitget swap markets.
    - Validates symbols and quantities.
    - Prepares order information.
    - Does NOT submit real orders yet.
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

    # ============================================================
    # INITIALIZE BITGET
    # ============================================================

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

            swap_symbols = [
                market_symbol
                for market_symbol, market in self.exchange.markets.items()
                if market.get("swap")
            ]

            logging.info(
                f"Bitget {self.environment} execution "
                "environment initialized."
            )

            logging.info(
                f"Loaded swap markets: {len(swap_symbols)}"
            )

            target_symbols = [
                "FET/USDT:USDT",
                "NEAR/USDT:USDT",
                "RENDER/USDT:USDT"
            ]

            available_targets = [
                symbol
                for symbol in target_symbols
                if symbol in self.exchange.markets
            ]

            logging.info(
                f"Target swap symbols: {available_targets}"
            )

            for symbol in target_symbols:
                if symbol in self.exchange.markets:
                    market = self.exchange.markets[symbol]

                    logging.info(
                        f"Execution market available: {symbol} | "
                        f"type={market.get('type')} | "
                        f"swap={market.get('swap')} | "
                        f"contract={market.get('contract')} | "
                        f"contractSize={market.get('contractSize')}"
                    )
                else:
                    logging.warning(
                        f"Execution market NOT found: {symbol}"
                    )

        except Exception as e:
            self.exchange = None

            logging.error(
                f"Bitget initialization error: {e}"
            )

    # ============================================================
    # READY CHECK
    # ============================================================

def fetch_equity(self):
        if not self.is_ready():
            return None

        # Diagnostic test: read Bitget futures account info only.
        try:
            logging.info(
                f"Bitget private API diagnostic: "
                f"environment={self.environment}, "
                f"ccxt_version={ccxt.__version__}"
            )

            response = (
                self.exchange.privateMixGetV2MixAccountAccounts(
                    {"productType": "USDT-FUTURES"}
                )
            )

            logging.info(
                "Bitget account-info diagnostic succeeded. "
                f"Response type={type(response).__name__}"
            )

        except Exception as e:
            logging.error(
                f"Bitget account-info diagnostic failed: "
                f"{type(e).__name__}: {e}"
            )

        # Existing balance test.
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

    # ============================================================
    # MARKET INFO
    # ============================================================

    def market_info(self, symbol):
        if not self.is_ready():
            return None

        try:
            if symbol not in self.exchange.markets:
                logging.warning(
                    f"Market not found: {symbol}"
                )
                return None

            market = self.exchange.market(symbol)

            limits = market.get("limits", {})
            amount_limits = limits.get("amount", {})
            price_limits = limits.get("price", {})
            precision = market.get("precision", {})

            return {
                "symbol": symbol,
                "contract": market.get("contract", False),
                "swap": market.get("swap", False),
                "contract_size": market.get("contractSize"),
                "amount_min": amount_limits.get("min"),
                "amount_max": amount_limits.get("max"),
                "price_min": price_limits.get("min"),
                "precision_amount": precision.get("amount"),
                "precision_price": precision.get("price")
            }

        except Exception as e:
            logging.error(
                f"Market info error {symbol}: {e}"
            )
            return None

    # ============================================================
    # NORMALIZE QUANTITY
    # ============================================================

    def normalize_quantity(self, symbol, quantity):
        if not self.is_ready():
            return None

        try:
            quantity = float(quantity)

            if quantity <= 0:
                logging.warning(
                    f"Invalid quantity: {quantity}"
                )
                return None

            logging.info(
                f"Execution market check: requested={symbol}"
            )

            symbol_exists = symbol in self.exchange.markets

            logging.info(
                f"Execution symbol exists={symbol_exists}"
            )

            if not symbol_exists:
                logging.error(
                    f"Execution symbol does not exist: {symbol}"
                )
                return None

            market = self.exchange.market(symbol)

            if not market.get("contract", False):
                logging.error(
                    f"Market is not a contract market: {symbol}"
                )
                return None

            formatted = self.exchange.amount_to_precision(
                symbol,
                quantity
            )

            normalized = float(formatted)

            if normalized <= 0:
                logging.error(
                    f"Normalized quantity is invalid: "
                    f"{symbol} quantity={normalized}"
                )
                return None

            minimum = (
                market
                .get("limits", {})
                .get("amount", {})
                .get("min")
            )

            if minimum is not None:
                minimum = float(minimum)

                if normalized < minimum:
                    logging.warning(
                        f"Quantity below exchange minimum: "
                        f"{symbol} "
                        f"quantity={normalized} "
                        f"minimum={minimum}"
                    )
                    return None

            logging.info(
                f"Quantity normalized successfully: "
                f"{symbol} "
                f"requested={quantity} "
                f"normalized={normalized}"
            )

            return normalized

        except Exception as e:
            logging.error(
                f"Quantity normalization error "
                f"{symbol}: {e}"
            )
            return None

    # ============================================================
    # VALIDATE ORDER
    # ============================================================

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
        if not self.is_ready():
            return {
                "valid": False,
                "error": "Execution exchange is not ready."
            }

        if direction not in ("LONG", "SHORT"):
            return {
                "valid": False,
                "error": f"Invalid direction: {direction}"
            }

        try:
            leverage = int(leverage)
        except Exception:
            return {
                "valid": False,
                "error": "Invalid leverage."
            }

        if leverage <= 0:
            return {
                "valid": False,
                "error": "Leverage must be greater than zero."
            }

        if leverage > Config.MAX_LEVERAGE:
            return {
                "valid": False,
                "error": (
                    f"Leverage {leverage} exceeds "
                    f"maximum allowed {Config.MAX_LEVERAGE}."
                )
            }

        try:
            entry = float(entry)
            stop = float(stop)
            tp1 = float(tp1)
            tp2 = float(tp2)
            quantity = float(quantity)
        except Exception:
            return {
                "valid": False,
                "error": "Invalid numeric order values."
            }

        if entry <= 0:
            return {
                "valid": False,
                "error": "Entry price must be greater than zero."
            }

        if quantity <= 0:
            return {
                "valid": False,
                "error": "Quantity must be greater than zero."
            }

        if direction == "LONG":
            if stop >= entry:
                return {
                    "valid": False,
                    "error": "LONG stop must be below entry."
                }

            if tp1 <= entry:
                return {
                    "valid": False,
                    "error": "LONG TP1 must be above entry."
                }

            if tp2 <= tp1:
                return {
                    "valid": False,
                    "error": "LONG TP2 must be above TP1."
                }

        else:
            if stop <= entry:
                return {
                    "valid": False,
                    "error": "SHORT stop must be above entry."
                }

            if tp1 >= entry:
                return {
                    "valid": False,
                    "error": "SHORT TP1 must be below entry."
                }

            if tp2 >= tp1:
                return {
                    "valid": False,
                    "error": "SHORT TP2 must be below TP1."
                }

        if symbol not in self.exchange.markets:
            return {
                "valid": False,
                "error": (
                    f"Exchange does not have market "
                    f"symbol: {symbol}"
                )
            }

        market = self.exchange.market(symbol)

        if not market.get("contract", False):
            return {
                "valid": False,
                "error": (
                    f"Market is not a contract market: "
                    f"{symbol}"
                )
            }

        if not market.get("swap", False):
            return {
                "valid": False,
                "error": (
                    f"Market is not a swap market: "
                    f"{symbol}"
                )
            }

        normalized_quantity = self.normalize_quantity(
            symbol,
            quantity
        )

        if normalized_quantity is None:
            return {
                "valid": False,
                "error": (
                    f"Quantity normalization failed "
                    f"for {symbol}."
                )
            }

        return {
            "valid": True,
            "error": None,
            "symbol": symbol,
            "direction": direction,
            "quantity": normalized_quantity,
            "leverage": leverage,
            "entry": entry,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2
        }

    # ============================================================
    # PREPARE ORDER
    # ============================================================

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
        validation = self.validate_order(
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            leverage=leverage,
            entry=entry,
            stop=stop,
            tp1=tp1,
            tp2=tp2
        )

        if not validation.get("valid"):
            return {
                "ready": False,
                "environment": self.environment,
                "symbol": symbol,
                "direction": direction,
                "error": validation.get("error")
            }

        normalized_quantity = validation["quantity"]

        if direction == "LONG":
            side = "buy"
            close_side = "sell"
        else:
            side = "sell"
            close_side = "buy"

        return {
            "ready": True,
            "environment": self.environment,
            "symbol": symbol,
            "direction": direction,
            "side": side,
            "close_side": close_side,
            "quantity": normalized_quantity,
            "leverage": validation["leverage"],
            "entry": validation["entry"],
            "stop": validation["stop"],
            "tp1": validation["tp1"],
            "tp2": validation["tp2"],
            "margin_mode": "isolated",
            "execution_enabled": False
        }

    # ============================================================
    # EXECUTE
    # ============================================================

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

        # Actual order submission is intentionally disabled
        # during the initial validation stage.

        return {
            "success": False,
            "executed": False,
            "environment": self.environment,
            "error": (
                "Order execution is disabled during "
                "the initial validation stage."
            )
        }


