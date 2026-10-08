import os
import json
import sqlite3
import threading
from datetime import datetime, date, timedelta
# ============================================================
# DATABASE
# ============================================================

class Database:
    def __init__(self, filename, initial_capital=None):
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        self.conn = sqlite3.connect(
            filename,
            check_same_thread=False
        )

        self.lock = threading.Lock()

        if initial_capital is None:
            initial_capital = float(
                os.getenv("CAPITAL", "1000")
            )

        self.initial_capital = initial_capital

        self.create_tables()
        self.initialize_portfolio(initial_capital)

    def create_tables(self):
        with self.lock:
            cur = self.conn.cursor()

            # ------------------------------------------------
            # SIGNALS
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                price REAL,
                tech_score REAL,
                ai_confidence REAL,
                ai_decision TEXT,
                setup TEXT,
                regime TEXT,
                entry REAL,
                stop REAL,
                tp1 REAL,
                tp2 REAL,
                risk_reward REAL,
                ai_reason TEXT,
                risk_flags TEXT,
                strategy_id TEXT,
                strategy_version TEXT,
                entry_method TEXT,
                market_regime TEXT,
                timeframe_profile TEXT,
                entry_timeframe TEXT,
                entry_score REAL,
                entry_confirmed INTEGER
            )
            """)

            # ------------------------------------------------
            # TRADES
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT,
                direction TEXT,
                entry REAL,
                stop REAL,
                exit REAL,
                quantity REAL,
                leverage REAL,
                pnl REAL,
                r_multiple REAL,
                result TEXT,
                opened_at TEXT,
                closed_at TEXT
            )
            """)

            # ------------------------------------------------
            # DAILY STATS
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                day TEXT PRIMARY KEY,
                pnl REAL DEFAULT 0,
                trades INTEGER DEFAULT 0
            )
            """)

            # ------------------------------------------------
            # PORTFOLIO STATE
            # One permanent row for the account
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initial_capital REAL DEFAULT 0,
                current_equity REAL DEFAULT 0,
                peak_equity REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                total_deposits REAL DEFAULT 0,
                total_withdrawals REAL DEFAULT 0,
                total_fees REAL DEFAULT 0,
                total_funding REAL DEFAULT 0,
                updated_at TEXT
            )
            """)

            # ------------------------------------------------
            # MONEY MOVEMENTS
            # Deposits / Withdrawals / Adjustments
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                transaction_type TEXT,
                amount REAL,
                balance_after REAL,
                note TEXT
            )
            """)

            # ------------------------------------------------
            # EQUITY HISTORY
            # Used for drawdown and long-term performance
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                equity REAL,
                peak_equity REAL,
                drawdown REAL
            )
            """)

            # ------------------------------------------------
            # LEARNING DATA
            # Stores the information surrounding each trade
            # so performance can be analyzed later.
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS learning_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                signal_id INTEGER,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                setup TEXT,
                regime TEXT,
                tech_score REAL,
                ai_confidence REAL,
                entry REAL,
                stop REAL,
                tp1 REAL,
                tp2 REAL,
                leverage REAL,
                outcome TEXT,
                pnl REAL,
                r_multiple REAL,
                holding_minutes REAL,
                features_json TEXT,
                created_at TEXT
            )
            """)

            self.conn.commit()

                # ------------------------------------------------
            # SIGNAL METADATA MIGRATION
            # ------------------------------------------------

            signal_columns = {
                "strategy_id": "TEXT",
                "strategy_version": "TEXT",
                "entry_method": "TEXT",
                "market_regime": "TEXT",
                "timeframe_profile": "TEXT",
                "entry_timeframe": "TEXT",
                "entry_score": "REAL",
                "entry_confirmed": "INTEGER"
            }

            cur.execute("""
                PRAGMA table_info(signals)
            """)

            existing_columns = {
                row[1]
                for row in cur.fetchall()
            }

            for column, column_type in signal_columns.items():
                if column not in existing_columns:
                    cur.execute(
                        f"""
                        ALTER TABLE signals
                        ADD COLUMN {column}
                        {column_type}
                        """
                    )

            self.conn.commit()

    # ========================================================
    # PORTFOLIO INITIALIZATION
    # ========================================================

    def initialize_portfolio(self, initial_capital):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT id
            FROM portfolio
            WHERE id = 1
            """)

            row = cur.fetchone()

            if not row:
                now = datetime.utcnow().isoformat()

                cur.execute("""
                INSERT INTO portfolio (
                    id,
                    initial_capital,
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    total_deposits,
                    total_withdrawals,
                    total_fees,
                    total_funding,
                    updated_at
                )
                VALUES (1, ?, ?, ?, 0, 0, 0, 0, 0, ?)
                """, (
                    initial_capital,
                    initial_capital,
                    initial_capital,
                    now
                ))

                cur.execute("""
                INSERT INTO portfolio_transactions (
                    timestamp,
                    transaction_type,
                    amount,
                    balance_after,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
                """, (
                    now,
                    "INITIAL_CAPITAL",
                    initial_capital,
                    initial_capital,
                    "Initial trading capital"
                ))

                cur.execute("""
                INSERT INTO equity_snapshots (
                    timestamp,
                    equity,
                    peak_equity,
                    drawdown
                )
                VALUES (?, ?, ?, ?)
                """, (
                    now,
                    initial_capital,
                    initial_capital,
                    0
                ))

                self.conn.commit()


    # ========================================================
    # PORTFOLIO INITIALIZATION
    # ========================================================

    def initialize_portfolio(self, initial_capital):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT id
            FROM portfolio
            WHERE id = 1
            """)

            row = cur.fetchone()

            if not row:
                now = datetime.utcnow().isoformat()

                cur.execute("""
                INSERT INTO portfolio (
                    id,
                    initial_capital,
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    total_deposits,
                    total_withdrawals,
                    total_fees,
                    total_funding,
                    updated_at
                )
                VALUES (1, ?, ?, ?, 0, 0, 0, 0, 0, ?)
                """, (
                    initial_capital,
                    initial_capital,
                    initial_capital,
                    now
                ))

                cur.execute("""
                INSERT INTO portfolio_transactions (
                    timestamp,
                    transaction_type,
                    amount,
                    balance_after,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
                """, (
                    now,
                    "INITIAL_CAPITAL",
                    initial_capital,
                    initial_capital,
                    "Initial trading capital"
                ))

                cur.execute("""
                INSERT INTO equity_snapshots (
                    timestamp,
                    equity,
                    peak_equity,
                    drawdown
                )
                VALUES (?, ?, ?, ?)
                """, (
                    now,
                    initial_capital,
                    initial_capital,
                    0
    # ========================================================
    # SAVE SIGNAL
    # ========================================================

    def save_signal(self, data):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            INSERT INTO signals (
                timestamp,
                symbol,
                direction,
                price,
                tech_score,
                ai_confidence,
                ai_decision,
                setup,
                regime,
                entry,
                stop,
                tp1,
                tp2,
                risk_reward,
                ai_reason,
                risk_flags,
                strategy_id,
                strategy_version,
                entry_method,
                market_regime,
                timeframe_profile,
                entry_timeframe,
                entry_score,
                entry_confirmed
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """, (
                datetime.utcnow().isoformat(),
                data["symbol"],
                data["direction"],
                data["price"],
                data["tech_score"],
                data["ai_confidence"],
                data["ai_decision"],
                data["setup"],
                data["regime"],
                data["entry"],
                data["stop"],
                data["tp1"],
                data["tp2"],
                data["risk_reward"],
                data["ai_reason"],
                json.dumps(data["risk_flags"]),
                data.get("strategy_id", "TREND_CONTINUATION"),
                data.get("strategy_version", "1.0"),
                data.get("entry_method", "PULLBACK"),
                data.get("market_regime", "UNKNOWN"),
                data.get(
                    "timeframe_profile",
                    "15m+1h+4h"
                ),
                data.get(
                    "entry_timeframe",
                    "5m"
                ),
                data.get("entry_score", 0),
                data.get("entry_confirmed", 0)
            ))

            self.conn.commit()

            return cur.lastrowid



    # ========================================================
    # OPEN TRADE
    # ========================================================

    def open_trade(
        self,
        signal_id,
        symbol,
        direction,
        entry,
        stop,
        quantity,
        leverage
    ):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            INSERT INTO trades (
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                datetime.utcnow().isoformat()
            ))

            self.conn.commit()

            return cur.lastrowid

    # ========================================================
    # CLOSE TRADE
    # ========================================================

    def close_trade(self, trade_id, exit_price):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            FROM trades
            WHERE id = ?
            """, (trade_id,))

            row = cur.fetchone()

            if not row:
                return None

            (
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            ) = row

            # -----------------------------------------------
            # Calculate PnL
            # -----------------------------------------------

            if direction == "LONG":
                pnl = (exit_price - entry) * quantity
            else:
                pnl = (entry - exit_price) * quantity

            risk = abs(entry - stop) * quantity

            r_multiple = (
                pnl / risk
                if risk > 0
                else 0
            )

            if pnl > 0:
                result = "WIN"
            elif pnl < 0:
                result = "LOSS"
            else:
                result = "BREAKEVEN"

            closed_at = datetime.utcnow().isoformat()

            # -----------------------------------------------
            # Holding time
            # -----------------------------------------------

            try:
                opened_dt = datetime.fromisoformat(opened_at)
                closed_dt = datetime.fromisoformat(closed_at)

                holding_minutes = (
                    closed_dt - opened_dt
                ).total_seconds() / 60

            except Exception:
                holding_minutes = 0

            # -----------------------------------------------
            # Update trade
            # -----------------------------------------------

            cur.execute("""
            UPDATE trades
            SET
                exit = ?,
                pnl = ?,
                r_multiple = ?,
                result = ?,
                closed_at = ?
            WHERE id = ?
            """, (
                exit_price,
                pnl,
                r_multiple,
                result,
                closed_at,
                trade_id
            ))

            # -----------------------------------------------
            # Update daily statistics
            # -----------------------------------------------

            day = closed_at[:10]

            cur.execute("""
            INSERT INTO daily_stats (
                day,
                pnl,
                trades
            )
            VALUES (?, ?, 1)
            ON CONFLICT(day)
            DO UPDATE SET
                pnl = pnl + excluded.pnl,
                trades = trades + 1
            """, (
                day,
                pnl
            ))

            # -----------------------------------------------
            # Update portfolio
            # -----------------------------------------------

            cur.execute("""
            SELECT
                initial_capital,
                current_equity,
                peak_equity,
                realized_pnl,
                total_deposits,
                total_withdrawals,
                total_fees,
                total_funding
            FROM portfolio
            WHERE id = 1
            """)

            portfolio = cur.fetchone()

            if portfolio:
                (
                    initial_capital,
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    total_deposits,
                    total_withdrawals,
                    total_fees,
                    total_funding
                ) = portfolio

                current_equity += pnl
                realized_pnl += pnl

                if current_equity > peak_equity:
                    peak_equity = current_equity

                drawdown = (
                    ((peak_equity - current_equity) / peak_equity) * 100
                    if peak_equity > 0
                    else 0
                )

                cur.execute("""
                UPDATE portfolio
                SET
                    current_equity = ?,
                    peak_equity = ?,
                    realized_pnl = ?,
                    updated_at = ?
                WHERE id = 1
                """, (
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    closed_at
                ))

                cur.execute("""
                INSERT INTO equity_snapshots (
                    timestamp,
                    equity,
                    peak_equity,
                    drawdown
                )
                VALUES (?, ?, ?, ?)
                """, (
                    closed_at,
                    current_equity,
                    peak_equity,
                    drawdown
                ))

            self.conn.commit()
# ============================================================
# DATABASE
# ============================================================

class Database:
    def __init__(self, filename, initial_capital=None):
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        self.conn = sqlite3.connect(
            filename,
            check_same_thread=False
        )

        self.lock = threading.Lock()

        if initial_capital is None:
            initial_capital = float(
                os.getenv("CAPITAL", "1000")
            )

        self.initial_capital = initial_capital

        self.create_tables()
        self.initialize_portfolio(initial_capital)

    def create_tables(self):
        with self.lock:
            cur = self.conn.cursor()

            # ------------------------------------------------
            # SIGNALS
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                price REAL,
                tech_score REAL,
                ai_confidence REAL,
                ai_decision TEXT,
                setup TEXT,
                regime TEXT,
                entry REAL,
                stop REAL,
                tp1 REAL,
                tp2 REAL,
                risk_reward REAL,
                ai_reason TEXT,
                risk_flags TEXT
            )
            """)

            # ------------------------------------------------
            # TRADES
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT,
                direction TEXT,
                entry REAL,
                stop REAL,
                exit REAL,
                quantity REAL,
                leverage REAL,
                pnl REAL,
                r_multiple REAL,
                result TEXT,
                opened_at TEXT,
                closed_at TEXT
            )
            """)

            # ------------------------------------------------
            # DAILY STATS
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                day TEXT PRIMARY KEY,
                pnl REAL DEFAULT 0,
                trades INTEGER DEFAULT 0
            )
            """)

            # ------------------------------------------------
            # PORTFOLIO STATE
            # One permanent row for the account
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initial_capital REAL DEFAULT 0,
                current_equity REAL DEFAULT 0,
                peak_equity REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                total_deposits REAL DEFAULT 0,
                total_withdrawals REAL DEFAULT 0,
                total_fees REAL DEFAULT 0,
                total_funding REAL DEFAULT 0,
                updated_at TEXT
            )
            """)

            # ------------------------------------------------
            # MONEY MOVEMENTS
            # Deposits / Withdrawals / Adjustments
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                transaction_type TEXT,
                amount REAL,
                balance_after REAL,
                note TEXT
            )
            """)

            # ------------------------------------------------
            # EQUITY HISTORY
            # Used for drawdown and long-term performance
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                equity REAL,
                peak_equity REAL,
                drawdown REAL
            )
            """)

            # ------------------------------------------------
            # LEARNING DATA
            # Stores the information surrounding each trade
            # so performance can be analyzed later.
            # ------------------------------------------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS learning_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                signal_id INTEGER,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                setup TEXT,
                regime TEXT,
                tech_score REAL,
                ai_confidence REAL,
                entry REAL,
                stop REAL,
                tp1 REAL,
                tp2 REAL,
                leverage REAL,
                outcome TEXT,
                pnl REAL,
                r_multiple REAL,
                holding_minutes REAL,
                features_json TEXT,
                created_at TEXT
            )
            """)

            self.conn.commit()

    # ========================================================
    # PORTFOLIO INITIALIZATION
    # ========================================================

    def initialize_portfolio(self, initial_capital):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT id
            FROM portfolio
            WHERE id = 1
            """)

            row = cur.fetchone()

            if not row:
                now = datetime.utcnow().isoformat()

                cur.execute("""
                INSERT INTO portfolio (
                    id,
                    initial_capital,
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    total_deposits,
                    total_withdrawals,
                    total_fees,
                    total_funding,
                    updated_at
                )
                VALUES (1, ?, ?, ?, 0, 0, 0, 0, 0, ?)
                """, (
                    initial_capital,
                    initial_capital,
                    initial_capital,
                    now
                ))

                cur.execute("""
                INSERT INTO portfolio_transactions (
                    timestamp,
                    transaction_type,
                    amount,
                    balance_after,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
                """, (
                    now,
                    "INITIAL_CAPITAL",
                    initial_capital,
                    initial_capital,
                    "Initial trading capital"
                ))

                cur.execute("""
                INSERT INTO equity_snapshots (
                    timestamp,
                    equity,
                    peak_equity,
                    drawdown
                )
                VALUES (?, ?, ?, ?)
                """, (
                    now,
                    initial_capital,
                    initial_capital,
                    0
                ))

                self.conn.commit()

    # ========================================================
    # SAVE SIGNAL
    # ========================================================

    def save_signal(self, data):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            INSERT INTO signals (
                timestamp,
                symbol,
                direction,
                price,
                tech_score,
                ai_confidence,
                ai_decision,
                setup,
                regime,
                entry,
                stop,
                tp1,
                tp2,
                risk_reward,
                ai_reason,
                risk_flags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                data["symbol"],
                data["direction"],
                data["price"],
                data["tech_score"],
                data["ai_confidence"],
                data["ai_decision"],
                data["setup"],
                data["regime"],
                data["entry"],
                data["stop"],
                data["tp1"],
                data["tp2"],
                data["risk_reward"],
                data["ai_reason"],
                json.dumps(data["risk_flags"])
            ))

            self.conn.commit()

            return cur.lastrowid

    # ========================================================
    # OPEN TRADE
    # ========================================================

    def open_trade(
        self,
        signal_id,
        symbol,
        direction,
        entry,
        stop,
        quantity,
        leverage
    ):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            INSERT INTO trades (
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                datetime.utcnow().isoformat()
            ))

            self.conn.commit()

            return cur.lastrowid

    # ========================================================
    # CLOSE TRADE
    # ========================================================

    def close_trade(self, trade_id, exit_price):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            FROM trades
            WHERE id = ?
            """, (trade_id,))

            row = cur.fetchone()

            if not row:
                return None

            (
                signal_id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            ) = row

            # -----------------------------------------------
            # Calculate PnL
            # -----------------------------------------------

            if direction == "LONG":
                pnl = (exit_price - entry) * quantity
            else:
                pnl = (entry - exit_price) * quantity

            risk = abs(entry - stop) * quantity

            r_multiple = (
                pnl / risk
                if risk > 0
                else 0
            )

            if pnl > 0:
                result = "WIN"
            elif pnl < 0:
                result = "LOSS"
            else:
                result = "BREAKEVEN"

            closed_at = datetime.utcnow().isoformat()

            # -----------------------------------------------
            # Holding time
            # -----------------------------------------------

            try:
                opened_dt = datetime.fromisoformat(opened_at)
                closed_dt = datetime.fromisoformat(closed_at)

                holding_minutes = (
                    closed_dt - opened_dt
                ).total_seconds() / 60

            except Exception:
                holding_minutes = 0

            # -----------------------------------------------
            # Update trade
            # -----------------------------------------------

            cur.execute("""
            UPDATE trades
            SET
                exit = ?,
                pnl = ?,
                r_multiple = ?,
                result = ?,
                closed_at = ?
            WHERE id = ?
            """, (
                exit_price,
                pnl,
                r_multiple,
                result,
                closed_at,
                trade_id
            ))

            # -----------------------------------------------
            # Update daily statistics
            # -----------------------------------------------

            day = closed_at[:10]

            cur.execute("""
            INSERT INTO daily_stats (
                day,
                pnl,
                trades
            )
            VALUES (?, ?, 1)
            ON CONFLICT(day)
            DO UPDATE SET
                pnl = pnl + excluded.pnl,
                trades = trades + 1
            """, (
                day,
                pnl
            ))

            # -----------------------------------------------
            # Update portfolio
            # -----------------------------------------------

            cur.execute("""
            SELECT
                initial_capital,
                current_equity,
                peak_equity,
                realized_pnl,
                total_deposits,
                total_withdrawals,
                total_fees,
                total_funding
            FROM portfolio
            WHERE id = 1
            """)

            portfolio = cur.fetchone()

            if portfolio:
                (
                    initial_capital,
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    total_deposits,
                    total_withdrawals,
                    total_fees,
                    total_funding
                ) = portfolio

                current_equity += pnl
                realized_pnl += pnl

                if current_equity > peak_equity:
                    peak_equity = current_equity

                drawdown = (
                    ((peak_equity - current_equity) / peak_equity) * 100
                    if peak_equity > 0
                    else 0
                )

                cur.execute("""
                UPDATE portfolio
                SET
                    current_equity = ?,
                    peak_equity = ?,
                    realized_pnl = ?,
                    updated_at = ?
                WHERE id = 1
                """, (
                    current_equity,
                    peak_equity,
                    realized_pnl,
                    closed_at
                ))

                cur.execute("""
                INSERT INTO equity_snapshots (
                    timestamp,
                    equity,
                    peak_equity,
                    drawdown
                )
                VALUES (?, ?, ?, ?)
                """, (
                    closed_at,
                    current_equity,
                    peak_equity,
                    drawdown
                ))

            # -----------------------------------------------
            # Save learning record
            # -----------------------------------------------

            self._save_learning_record(
                cur=cur,
                trade_id=trade_id,
                signal_id=signal_id,
                symbol=symbol,
                direction=direction,
                entry=entry,
                stop=stop,
                leverage=leverage,
                result=result,
                pnl=pnl,
                r_multiple=r_multiple,
                holding_minutes=holding_minutes
            )

            self.conn.commit()

            return {
                "pnl": pnl,
                "r": r_multiple,
                "result": result,
                "holding_minutes": holding_minutes
            }

    # ========================================================
    # LEARNING RECORD
    # ========================================================

    def _save_learning_record(
        self,
        cur,
        trade_id,
        signal_id,
        symbol,
        direction,
        entry,
        stop,
        leverage,
        result,
        pnl,
        r_multiple,
        holding_minutes
    ):
        signal_data = {}

        if signal_id:
            cur.execute("""
            SELECT
                setup,
                regime,
                tech_score,
                ai_confidence,
                entry,
                stop,
                tp1,
                tp2
            FROM signals
            WHERE id = ?
            """, (signal_id,))

            row = cur.fetchone()

            if row:
                (
                    setup,
                    regime,
                    tech_score,
                    ai_confidence,
                    signal_entry,
                    signal_stop,
                    tp1,
                    tp2
                ) = row

                signal_data = {
                    "setup": setup,
                    "regime": regime,
                    "tech_score": tech_score,
                    "ai_confidence": ai_confidence,
                    "signal_entry": signal_entry,
                    "signal_stop": signal_stop,
                    "tp1": tp1,
                    "tp2": tp2
                }

        cur.execute("""
        INSERT INTO learning_records (
            trade_id,
            signal_id,
            timestamp,
            symbol,
            direction,
            setup,
            regime,
            tech_score,
            ai_confidence,
            entry,
            stop,
            tp1,
            tp2,
            leverage,
            outcome,
            pnl,
            r_multiple,
            holding_minutes,
            features_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            signal_id,
            datetime.utcnow().isoformat(),
            symbol,
            direction,
            signal_data.get("setup"),
            signal_data.get("regime"),
            signal_data.get("tech_score"),
            signal_data.get("ai_confidence"),
            entry,
            stop,
            signal_data.get("tp1"),
            signal_data.get("tp2"),
            leverage,
            result,
            pnl,
            r_multiple,
            holding_minutes,
            json.dumps(signal_data),
            datetime.utcnow().isoformat()
        ))

    # ========================================================
    # DEPOSIT
    # ========================================================

    def add_deposit(self, amount, note=""):
        if amount <= 0:
            return False

        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT current_equity, peak_equity
            FROM portfolio
            WHERE id = 1
            """)

            row = cur.fetchone()

            if not row:
                return False

            current_equity, peak_equity = row

            current_equity += amount

            if current_equity > peak_equity:
                peak_equity = current_equity

            now = datetime.utcnow().isoformat()

            cur.execute("""
            UPDATE portfolio
            SET
                current_equity = ?,
                peak_equity = ?,
                total_deposits = total_deposits + ?,
                updated_at = ?
            WHERE id = 1
            """, (
                current_equity,
                peak_equity,
                amount,
                now
            ))

            cur.execute("""
            INSERT INTO portfolio_transactions (
                timestamp,
                transaction_type,
                amount,
                balance_after,
                note
            )
            VALUES (?, 'DEPOSIT', ?, ?, ?)
            """, (
                now,
                amount,
                current_equity,
                note
            ))

            self.conn.commit()

            return True

    # ========================================================
    # WITHDRAWAL
    # ========================================================

    def add_withdrawal(self, amount, note=""):
        if amount <= 0:
            return False

        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT current_equity
            FROM portfolio
            WHERE id = 1
            """)

            row = cur.fetchone()

            if not row:
                return False

            current_equity = row[0]

            current_equity -= amount

            now = datetime.utcnow().isoformat()

            cur.execute("""
            UPDATE portfolio
            SET
                current_equity = ?,
                total_withdrawals = total_withdrawals + ?,
                updated_at = ?
            WHERE id = 1
            """, (
                current_equity,
                amount,
                now
            ))

            cur.execute("""
            INSERT INTO portfolio_transactions (
                timestamp,
                transaction_type,
                amount,
                balance_after,
                note
            )
            VALUES (?, 'WITHDRAWAL', ?, ?, ?)
            """, (
                now,
                amount,
                current_equity,
                note
            ))

            self.conn.commit()

            return True

    # ========================================================
    # PORTFOLIO STATUS
    # ========================================================

    def portfolio_stats(self):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT
                initial_capital,
                current_equity,
                peak_equity,
                realized_pnl,
                total_deposits,
                total_withdrawals,
                total_fees,
                total_funding,
                updated_at
            FROM portfolio
            WHERE id = 1
            """)

            row = cur.fetchone()

            if not row:
                return None

            (
                initial_capital,
                current_equity,
                peak_equity,
                realized_pnl,
                total_deposits,
                total_withdrawals,
                total_fees,
                total_funding,
                updated_at
            ) = row

            drawdown = (
                ((peak_equity - current_equity) / peak_equity) * 100
                if peak_equity > 0
                else 0
            )

            return {
                "initial_capital": initial_capital,
                "current_equity": current_equity,
                "peak_equity": peak_equity,
                "realized_pnl": realized_pnl,
                "total_deposits": total_deposits,
                "total_withdrawals": total_withdrawals,
                "total_fees": total_fees,
                "total_funding": total_funding,
                "drawdown_pct": drawdown,
                "updated_at": updated_at
            }

    # ========================================================
    # OPEN TRADES
    # ========================================================

    def get_open_trades(self):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT
                id,
                symbol,
                direction,
                entry,
                stop,
                quantity,
                leverage,
                opened_at
            FROM trades
            WHERE exit IS NULL
            """)

            return cur.fetchall()

    # ========================================================
    # DAILY PNL
    # ========================================================

    def get_daily_pnl(self, day=None):
        with self.lock:
            cur = self.conn.cursor()

            if day is None:
                day = datetime.utcnow().strftime("%Y-%m-%d")

            cur.execute("""
            SELECT
                COALESCE(pnl, 0),
                COALESCE(trades, 0)
            FROM daily_stats
            WHERE day = ?
            """, (day,))

            row = cur.fetchone()

            if not row:
                return {
                    "pnl": 0,
                    "trades": 0
                }

            return {
                "pnl": row[0],
                "trades": row[1]
            }

    # ========================================================
    # GENERAL TRADING STATS
    # ========================================================

    def stats(self):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            SELECT
                COUNT(*),
                SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END),
                SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END),
                COALESCE(SUM(pnl), 0),
                COALESCE(AVG(r_multiple), 0)
            FROM trades
            WHERE exit IS NOT NULL
            """)

            row = cur.fetchone()

            total = row[0] or 0
            wins = row[1] or 0
            losses = row[2] or 0
            pnl = row[3] or 0
            avg_r = row[4] or 0

            win_rate = (
                wins / total * 100
                if total
                else 0
            )

            cur.execute("""
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN pnl > 0 THEN pnl
                            ELSE 0
                        END
                    ),
                    0
                ),
                COALESCE(
                    ABS(
                        SUM(
                            CASE
                                WHEN pnl < 0 THEN pnl
                                ELSE 0
                            END
                        )
                    ),
                    0
                )
            FROM trades
            WHERE exit IS NOT NULL
            """)

            gross_profit, gross_loss = cur.fetchone()

            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else 0
            )

            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "pnl": pnl,
                "avg_r": avg_r,
                "profit_factor": profit_factor
            }
