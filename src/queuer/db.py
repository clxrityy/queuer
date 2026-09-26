from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    qotd_channel_id INTEGER,
    timezone TEXT NOT NULL,
    schedule_time TEXT,
    schedule_enabled INTEGER NOT NULL DEFAULT 0,
    reminder_interval_minutes INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (guild_id, role_id, purpose),
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    creator_user_id INTEGER NOT NULL,
    current_step TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    draft_id INTEGER,
    status TEXT NOT NULL,
    type TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    scheduled_for TEXT,
    target_user_id INTEGER,
    created_by_user_id INTEGER NOT NULL,
    approved_by_user_id INTEGER,
    approved_at TEXT,
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE,
    FOREIGN KEY (draft_id) REFERENCES question_drafts (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS send_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    queue_item_id INTEGER,
    status TEXT NOT NULL,
    error_message TEXT,
    sent_message_id INTEGER,
    sent_channel_id INTEGER,
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE,
    FOREIGN KEY (queue_item_id) REFERENCES queue_items (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS active_threads (
    guild_id INTEGER PRIMARY KEY,
    queue_item_id INTEGER NOT NULL,
    thread_channel_id INTEGER NOT NULL,
    locked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE,
    FOREIGN KEY (queue_item_id) REFERENCES queue_items (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vote_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    queue_item_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    selected_option TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (queue_item_id, user_id),
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE,
    FOREIGN KEY (queue_item_id) REFERENCES queue_items (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member_selection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    selected_for_queue_item_id INTEGER,
    selected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id) ON DELETE CASCADE,
    FOREIGN KEY (selected_for_queue_item_id) REFERENCES queue_items (id) ON DELETE SET NULL
);
"""


async def initialize_database(database_path: Path, guild_id: int, default_timezone: str) -> None:
    database = Database(database_path)
    await database.initialize(guild_id=guild_id, default_timezone=default_timezone)


class Database:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.database_path)
        connection.row_factory = aiosqlite.Row
        try:
            await connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            await connection.close()

    async def initialize(self, *, guild_id: int, default_timezone: str) -> None:
        async with self.connection() as connection:
            await connection.executescript(SCHEMA_SQL)
            await self._ensure_queue_items_columns(connection)
            await connection.execute(
                """
                INSERT INTO guild_settings (guild_id, timezone)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO NOTHING
                """,
                (guild_id, default_timezone),
            )
            await connection.commit()

    async def _ensure_queue_items_columns(self, connection: aiosqlite.Connection) -> None:
        cursor = await connection.execute("PRAGMA table_info(queue_items)")
        rows = await cursor.fetchall()
        column_names = {row["name"] for row in rows}
        if "scheduled_for" not in column_names:
            await connection.execute("ALTER TABLE queue_items ADD COLUMN scheduled_for TEXT")
