class TelegramUI:

    @staticmethod
    def status_message(
        mode,
        symbols_count,
        open_trades_count
    ):
        return (
            "🤖 BOT STATUS\n\n"
            f"Mode: {mode}\n"
            "Market: Bitget USDT-M\n"
            "Margin: Isolated\n"
            f"Symbols: {symbols_count}\n"
            f"Open journal trades: {open_trades_count}"
        )

    @staticmethod
    def equity_message(environment, equity):
        return (
            "💰 EXCHANGE EQUITY\n\n"
            f"Environment: {environment}\n"
            f"USDT Equity: ${equity:.2f}"
        )

    @staticmethod
    def stats_message(stats):
        return (
            "📊 BOT STATISTICS\n\n"
            f"Trades: {stats['total']}\n"
            f"Wins: {stats['wins']}\n"
            f"Losses: {stats['losses']}\n"
            f"Win Rate: {stats['win_rate']:.2f}%\n"
            f"Total PnL: ${stats['pnl']:.2f}\n"
            f"Average R: {stats['avg_r']:.3f}\n"
            f"Profit Factor: {stats['profit_factor']:.2f}"
        )

    @staticmethod
    def manual_open_message():
        return (
            "Manual trade registration will be "
            "handled after ExecutionEngine is added."
        )

    @staticmethod
    def manual_order_disabled_message():
        return (
            "⚠️ Manual order registration is "
            "temporarily disabled while the "
            "new execution layer is being installed."
        )

    @staticmethod
    def close_usage_message():
        return "/close TRADE_ID EXIT_PRICE"

    @staticmethod
    def trade_not_found_message():
        return "❌ Trade not found."

    @staticmethod
    def trade_closed_message(result):
        return (
            "🏁 TRADE CLOSED\n"
            f"Result: {result['result']}\n"
            f"PnL: ${result['pnl']:.2f}\n"
            f"R: {result['r']:.2f}"
        )

    @staticmethod
    def invalid_close_message():
        return "❌ Invalid close command."
