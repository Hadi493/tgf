import aiosqlite
from loguru import logger
import os

DB_PATH = "db/storage.db"

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def initialize(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS seen_messages (
                    content_hash TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("Database initialized.")

    async def is_duplicate(self, content_hash: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM seen_messages WHERE content_hash = ?", (content_hash,)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def mark_as_seen(self, content_hash: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO seen_messages (content_hash) VALUES (?)", (content_hash,)
            )
            await db.commit()
