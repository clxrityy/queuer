from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from ..db import Database
from ..models import QueueItem
from ._shared import isoformat_utc


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
        scheduled_for: Optional[datetime],
        target_user_id: Optional[int],
        approved_by_user_id: int,
    ) -> QueueItem:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO queue_items (
                    guild_id, draft_id, status, type, prompt_text, payload_json, scheduled_for,
                    target_user_id, created_by_user_id, approved_by_user_id, approved_at, position
                )
                SELECT ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                       COALESCE(MAX(position), 0) + 1
                FROM queue_items
                WHERE guild_id = ?
                """,
                (
                    guild_id,
                    draft_id,
                    question_type,
                    prompt_text,
                    json.dumps(payload),
                    isoformat_utc(scheduled_for) if scheduled_for is not None else None,
                    target_user_id,
                    creator_user_id,
                    approved_by_user_id,
                    guild_id,
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

    async def get(self, queue_item_id: int) -> Optional[QueueItem]:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, draft_id, status, type, prompt_text, payload_json,
                       scheduled_for, target_user_id, created_by_user_id, approved_by_user_id, approved_at,
                       position, created_at, updated_at
                FROM queue_items
                WHERE id = ?
                """,
                (queue_item_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._hydrate_queue_item(row)

    async def list_for_guild(self, guild_id: int, *, status: Optional[str] = None) -> list[QueueItem]:
        query = """
            SELECT id, guild_id, draft_id, status, type, prompt_text, payload_json,
                   scheduled_for, target_user_id, created_by_user_id, approved_by_user_id, approved_at,
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

        return [self._hydrate_queue_item(row) for row in rows]

    async def get_next_queued(self, guild_id: int) -> Optional[QueueItem]:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, draft_id, status, type, prompt_text, payload_json,
                       scheduled_for, target_user_id, created_by_user_id, approved_by_user_id, approved_at,
                       position, created_at, updated_at
                FROM queue_items
                WHERE guild_id = ?
                  AND status = 'queued'
                ORDER BY position ASC
                LIMIT 1
                """,
                (guild_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._hydrate_queue_item(row)

    async def get_latest_successful_send(self, guild_id: int) -> Optional[str]:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT sent_at
                FROM send_events
                WHERE guild_id = ?
                  AND status = 'sent'
                  AND sent_at IS NOT NULL
                ORDER BY datetime(sent_at) DESC
                LIMIT 1
                """,
                (guild_id,),
            )
            row = await cursor.fetchone()

        return None if row is None else row["sent_at"]

    async def mark_sent(self, queue_item_id: int) -> None:
        async with self.database.connection() as connection:
            await connection.execute(
                """
                UPDATE queue_items
                SET status = 'sent',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (queue_item_id,),
            )
            await connection.commit()

    async def delete_queued_item(self, guild_id: int, queue_item_id: int) -> bool:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT position
                FROM queue_items
                WHERE guild_id = ?
                  AND id = ?
                  AND status = 'queued'
                """,
                (guild_id, queue_item_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return False

            removed_position = int(row["position"])
            await connection.execute(
                """
                DELETE FROM queue_items
                WHERE guild_id = ?
                  AND id = ?
                  AND status = 'queued'
                """,
                (guild_id, queue_item_id),
            )
            await connection.execute(
                """
                UPDATE queue_items
                SET position = position - 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND status = 'queued'
                  AND position > ?
                """,
                (guild_id, removed_position),
            )
            await connection.commit()
        return True

    async def record_send_event(
        self,
        guild_id: int,
        *,
        queue_item_id: Optional[int],
        status: str,
        error_message: Optional[str] = None,
        sent_message_id: Optional[int] = None,
        sent_channel_id: Optional[int] = None,
        sent_at: Optional[datetime] = None,
    ) -> None:
        async with self.database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO send_events (
                    guild_id, queue_item_id, status, error_message,
                    sent_message_id, sent_channel_id, sent_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    queue_item_id,
                    status,
                    error_message,
                    sent_message_id,
                    sent_channel_id,
                    isoformat_utc(sent_at) if sent_at is not None else None,
                ),
            )
            await connection.commit()

    async def list_recent_member_selection_user_ids(
        self,
        guild_id: int,
        *,
        eligible_user_ids: list[int],
    ) -> list[int]:
        if not eligible_user_ids:
            return []

        placeholders = ", ".join("?" for _ in eligible_user_ids)
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                f"""
                SELECT user_id
                FROM member_selection_history
                WHERE guild_id = ?
                  AND user_id IN ({placeholders})
                ORDER BY datetime(selected_at) DESC, id DESC
                """,
                [guild_id, *eligible_user_ids],
            )
            rows = await cursor.fetchall()

        return [int(row["user_id"]) for row in rows]

    async def record_member_selection(self, guild_id: int, *, user_id: int, queue_item_id: int) -> None:
        async with self.database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO member_selection_history (guild_id, user_id, selected_for_queue_item_id)
                VALUES (?, ?, ?)
                """,
                (guild_id, user_id, queue_item_id),
            )
            await connection.commit()

    async def mark_pending_reconfirmation(self, queue_item_id: int, payload: dict[str, object], prompt_text: str) -> None:
        cleaned_prompt_text = prompt_text.strip()
        if not cleaned_prompt_text:
            raise ValueError("Queue item prompt_text cannot be empty")

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
                (json.dumps(payload), cleaned_prompt_text, queue_item_id),
            )
            await connection.commit()

    def _hydrate_queue_item(self, row) -> QueueItem:
        return QueueItem(
            id=row["id"],
            guild_id=row["guild_id"],
            draft_id=row["draft_id"],
            status=row["status"],
            type=row["type"],
            prompt_text=row["prompt_text"],
            payload_json=row["payload_json"],
            scheduled_for=row["scheduled_for"],
            target_user_id=row["target_user_id"],
            created_by_user_id=row["created_by_user_id"],
            approved_by_user_id=row["approved_by_user_id"],
            approved_at=row["approved_at"],
            position=row["position"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
