import aiosqlite
import os

DB_PATH = "db/storage.db"

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.connection = None

    async def connect(self):
        if not self.connection:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row
            await self.initialize()

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def initialize(self):
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS seen_messages (
                content_hash TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS message_mappings (
                source_chat_id INTEGER,
                source_msg_id INTEGER,
                aggregator_msg_id INTEGER,
                PRIMARY KEY (source_chat_id, source_msg_id)
            )
        """)
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_mappings_source ON message_mappings (source_chat_id, source_msg_id)"
        )
        await self.connection.commit()

    async def is_duplicate(self, content_hash: str) -> bool:
        async with self.connection.execute(
            "SELECT 1 FROM seen_messages WHERE content_hash = ?", (content_hash,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_as_seen(self, content_hash: str):
        await self.connection.execute(
            "INSERT OR IGNORE INTO seen_messages (content_hash) VALUES (?)", (content_hash,)
        )
        await self.connection.commit()

    async def save_mapping(self, source_chat_id: int, source_msg_id: int, aggregator_msg_id: int):
        await self.connection.execute(
            "INSERT OR REPLACE INTO message_mappings (source_chat_id, source_msg_id, aggregator_msg_id) VALUES (?, ?, ?)",
            (source_chat_id, source_msg_id, aggregator_msg_id)
        )
        await self.connection.commit()

    async def get_mapping(self, source_chat_id: int, source_msg_id: int) -> int | None:
        async with self.connection.execute(
            "SELECT aggregator_msg_id FROM message_mappings WHERE source_chat_id = ? AND source_msg_id = ?",
            (source_chat_id, source_msg_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row["aggregator_msg_id"] if row else None

    async def get_last_message_id(self, source_chat_id: int) -> int:
        async with self.connection.execute(
            "SELECT MAX(source_msg_id) FROM message_mappings WHERE source_chat_id = ?", (source_chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 0

    async def get_stats(self) -> dict:
        async with self.connection.execute("SELECT count(*) FROM seen_messages") as cursor:
            total_seen = (await cursor.fetchone())[0]
        async with self.connection.execute("SELECT count(*) FROM message_mappings") as cursor:
            total_forwarded = (await cursor.fetchone())[0]
        return {
            "total_seen": total_seen,
            "total_forwarded": total_forwarded
        }
