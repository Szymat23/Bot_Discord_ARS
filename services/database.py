import secrets
import aiosqlite
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("CasinoBot")


class DatabaseHandler:
    def __init__(self, db_path, config):
        self.db_path = db_path
        self.default_balance = config["bot_settings"]["default_balance"]
        self.default_bet = config["slots_settings"]["default_bet"]
        self.token_expiry_time = config["payments"]["expiry_time_token"]

    async def setup(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT {self.default_balance}
                )
            """)

            await self._remove_win_rate_column_if_exists(db)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game_type TEXT,
                    bet INTEGER,
                    win_amount INTEGER,
                    timestamp TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS transaction_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_token VARCHAR(64),
                    is_active BOOLEAN NOT NULL DEFAULT false,
                    expiry_time TEXT
                )
            """)
            await db.commit()
            logger.info("Baza danych została zainicjalizowana pomyślnie.")

    async def _remove_win_rate_column_if_exists(self, db):
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = await cursor.fetchall()

        column_names = [column[1] for column in columns]

        if "win_rate" not in column_names:
            return

        logger.info("Wykryto starą kolumnę users.win_rate. Trwa migracja bazy.")

        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS users_new (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT {self.default_balance}
            )
        """)

        await db.execute("""
            INSERT OR REPLACE INTO users_new (user_id, balance)
            SELECT user_id, balance FROM users
        """)

        await db.execute("DROP TABLE users")
        await db.execute("ALTER TABLE users_new RENAME TO users")
        logger.info("Usunięto kolumnę users.win_rate z bazy danych.")

    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()

                if row:
                    return {"balance": row[0]}

                await db.execute(
                    "INSERT INTO users (user_id, balance) VALUES (?, ?)",
                    (user_id, self.default_balance)
                )
                await db.commit()
                return {"balance": self.default_balance}

    async def update_balance(self, user_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()

    async def add_log(self, user_id: int, game_type: str, bet: int, win_amount: int):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO logs (user_id, game_type, bet, win_amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user_id, game_type, bet, win_amount, now)
            )
            await db.commit()

    async def get_user_history(self, user_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT game_type, bet, win_amount, timestamp FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_user_stats(self, user_id: int, hours: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT
                    COUNT(*) as total_games,
                    SUM(CASE WHEN win_amount > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN win_amount = 0 THEN 1 ELSE 0 END) as losses,
                    AVG(win_amount) as avg_win,
                    SUM(win_amount) - SUM(bet) as net_profit
                FROM logs
                WHERE user_id = ?
            """
            params = [user_id]

            if hours:
                query += " AND timestamp >= datetime('now', ?)"
                params.append(f'-{hours} hours')

            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                if not row or row["total_games"] == 0:
                    return {"total_games": 0, "wins": 0, "losses": 0, "avg_win": 0, "net_profit": 0}
                return dict(row)

    async def generate_payment_token(self, user_id: int):
        exp_time = (datetime.now() + timedelta(minutes=self.token_expiry_time)).strftime("%Y-%m-%d %H:%M:%S")
        user_token = secrets.token_urlsafe(32)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO transaction_tokens (user_id, user_token, is_active, expiry_time) VALUES (?, ?, ?, ?)",
                (user_id, user_token, True, exp_time)
            )
            await db.commit()
            return user_token

    async def deactive_token(self, user_token: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE transaction_tokens SET is_active = false WHERE user_token = ?",
                (user_token,)
            )
            await db.commit()

    async def make_payment(self, user_token: str, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM transaction_tokens WHERE user_token = ?",
                (user_token,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                return "Blad"

            expiry_time = datetime.strptime(row["expiry_time"], "%Y-%m-%d %H:%M:%S")
            if row["is_active"] and datetime.now() < expiry_time:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, row["user_id"])
                )
                await db.execute(
                    "UPDATE transaction_tokens SET is_active = false WHERE user_token = ?",
                    (user_token,)
                )
                await db.commit()
                return "Sukces"
            return "Blad"

    async def deactivate_expired_tokens(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE transaction_tokens
                SET is_active = false
                WHERE is_active = true
                AND datetime(expiry_time) <= datetime('now')
                """
            )
            await db.commit()
