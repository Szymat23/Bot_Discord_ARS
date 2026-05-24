import secrets
import aiosqlite
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("EconomyBot")


class DatabaseHandler:
    def __init__(self, db_path, config):
        self.db_path = db_path
        self.default_balance = config["bot_settings"]["default_balance"]
        self.token_expiry_time = config["topup_settings"]["expiry_time_token"]

    async def setup(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT {self.default_balance}
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    activity_type TEXT,
                    entry_cost INTEGER,
                    reward_amount INTEGER,
                    timestamp TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS topup_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_token VARCHAR(64),
                    topup_code TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT false,
                    expiry_time TEXT
                )
            """)

            await db.commit()
            logger.info("Baza danych została zainicjalizowana pomyślnie.")

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
        await self.get_user(user_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()

    async def add_log(self, user_id: int, activity_type: str, entry_cost: int, reward_amount: int):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO logs (user_id, activity_type, entry_cost, reward_amount, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, activity_type, entry_cost, reward_amount, now)
            )
            await db.commit()

    async def get_user_history(self, user_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT activity_type, entry_cost, reward_amount, timestamp
                FROM logs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
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
                    SUM(CASE WHEN reward_amount > 0 THEN 1 ELSE 0 END) as successful_rounds,
                    SUM(CASE WHEN reward_amount = 0 THEN 1 ELSE 0 END) as empty_rounds,
                    AVG(reward_amount) as avg_reward,
                    SUM(reward_amount) - SUM(entry_cost) as net_change
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
                    return {
                        "total_games": 0,
                        "successful_rounds": 0,
                        "empty_rounds": 0,
                        "avg_reward": 0,
                        "net_change": 0
                    }
                return dict(row)

    async def generate_topup_token(self, user_id: int):
        await self.get_user(user_id)
        exp_time = (datetime.now() + timedelta(minutes=self.token_expiry_time)).strftime("%Y-%m-%d %H:%M:%S")
        user_token = secrets.token_urlsafe(32)
        topup_code = f"{secrets.randbelow(1000000):06d}"

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO topup_tokens (user_id, user_token, topup_code, is_active, expiry_time)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, user_token, topup_code, True, exp_time)
            )
            await db.commit()
            return user_token, topup_code

    async def deactivate_token(self, user_token: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE topup_tokens SET is_active = false WHERE user_token = ?",
                (user_token,)
            )
            await db.commit()

    async def make_topup(self, user_token: str, amount: int, topup_code: str):
        if amount <= 0:
            return {"status": "Blad"}

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM topup_tokens WHERE user_token = ?",
                (user_token,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                return {"status": "Blad"}

            expiry_time = datetime.strptime(row["expiry_time"], "%Y-%m-%d %H:%M:%S")
            code_is_valid = row["topup_code"] == topup_code

            if row["is_active"] and datetime.now() < expiry_time and code_is_valid:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, row["user_id"])
                )
                await db.execute(
                    "UPDATE topup_tokens SET is_active = false WHERE user_token = ?",
                    (user_token,)
                )
                await db.commit()
                return {"status": "Sukces", "user_id": row["user_id"], "amount": amount}
            return {"status": "Blad"}

    async def deactivate_expired_tokens(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE topup_tokens
                SET is_active = false
                WHERE is_active = true
                AND datetime(expiry_time) <= datetime('now')
                """
            )
            await db.commit()
