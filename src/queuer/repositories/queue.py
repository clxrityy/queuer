from __future__ import annotations

import json

from ..db import Database
from ..models import QueueItem


class QueueRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_from_draft(
        self,
        guild_id: int,
        draft_id: int,
        creator_user_id: int,
        *,
        question_type: str,
        prompt_text: str,
        payload: dict[str, object],
        target_user_id: int | None,
        approved_by_user_id: int,
    ) -> QueueItem:
        position = await self._next_position(guild_id)
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO queue_items (
                    guild_id, draft_id, status, type, prompt_text, payload_json,
                    target_user_id, created_by_user_id, approved_by_user_id, approved_at, position
                )
                VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    guild_id,
                    draft_id,
                    question_type,
                    prompt_text,
                    json.dumps(payload),
                    target_user_id,
                    creator_user_id,
                    approved_by_user_id,
                    position,
                ),
            )
            await connection.commit()
            queue_item_id = cursor.lastrowid

        if queue_item_id is None:
            raise RuntimeError("Queue item creation succeeded but no row ID was returned")

        queue_item = await self.get(queue_item_id)
        if queue_item is None:
            raise RuntimeError("Queue item creation succeeded but the item could not be reloaded")
        return queue_item

    async def get(self, queue_item_id: int) -> QueueItem | None:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, draft_id, status, type, prompt_text, payload_json,
                       target_user_id, created_by_user_id, approved_by_user_id, approved_at,
                       position, created_at, updated_at
                FROM queue_items
                WHERE id = ?
                """,
                (queue_item_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return QueueItem(
            id=row["id"],
            guild_id=row["guild_id"],
            draft_id=row["draft_id"],
            status=row["status"],
            type=row["type"],
            prompt_text=row["prompt_text"],
            payload_json=row["payload_json"],
            target_user_id=row["target_user_id"],
            created_by_user_id=row["created_by_user_id"],
            approved_by_user_id=row["approved_by_user_id"],
            approved_at=row["approved_at"],
            position=row["position"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_for_guild(self, guild_id: int, *, status: str | None = None) -> list[QueueItem]:
        query = """
            SELECT id, guild_id, draft_id, status, type, prompt_text, payload_json,
                   target_user_id, created_by_user_id, approved_by_user_id, approved_at,
                   position, created_at, updated_at
            FROM queue_items
            WHERE guild_id = ?
        """
        params: list[object] = [guild_id]
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY position ASC"

        async with self.database.connection() as connection:
            cursor = await connection.execute(query, params)
            rows = await cursor.fetchall()

        return [
            QueueItem(
                id=row["id"],
                guild_id=row["guild_id"],
                draft_id=row["draft_id"],
                status=row["status"],
                type=row["type"],
                prompt_text=row["prompt_text"],
                payload_json=row["payload_json"],
                target_user_id=row["target_user_id"],
                created_by_user_id=row["created_by_user_id"],
                approved_by_user_id=row["approved_by_user_id"],
                approved_at=row["approved_at"],
                position=row["position"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def mark_pending_reconfirmation(self, queue_item_id: int, payload: dict[str, object], prompt_text: str) -> None:
        async with self.database.connection() as connection:
            await connection.execute(
                """
                UPDATE queue_items
                SET status = 'pending_reconfirmation',
                    payload_json = ?,
                    prompt_text = ?,
                    approved_by_user_id = NULL,
                    approved_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(payload), prompt_text, queue_item_id),
            )
            await connection.commit()

    async def _next_position(self, guild_id: int) -> int:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM queue_items WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
        next_position = row["next_position"] if row is not None else 1
        return int(next_position)