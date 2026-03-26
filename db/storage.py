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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS message_mappings (
                    source_chat_id INTEGER,
                    source_msg_id INTEGER,
                    aggregator_msg_id INTEGER,
                    PRIMARY KEY (source_chat_id, source_msg_id)
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_mappings_source ON message_mappings (source_chat_id, source_msg_id)")
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

    async def save_mapping(self, source_chat_id: int, source_msg_id: int, aggregator_msg_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO message_mappings (source_chat_id, source_msg_id, aggregator_msg_id) VALUES (?, ?, ?)",
                (source_chat_id, source_msg_id, aggregator_msg_id)
            )
            await db.commit()

    async def get_mapping(self, source_chat_id: int, source_msg_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT aggregator_msg_id FROM message_mappings WHERE source_chat_id = ? AND source_msg_id = ?",
                (source_chat_id, source_msg_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_last_message_id(self, source_chat_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT MAX(source_msg_id) FROM message_mappings WHERE source_chat_id = ?", (source_chat_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else 0
