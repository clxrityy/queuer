from __future__ import annotations

import json
from datetime import datetime

from .db import Database
from .models import GuildSettings, QuestionDraft, QueueItem, RoleAssignment


def _isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


class GuildSettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(self, guild_id: int) -> GuildSettings | None:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT guild_id, qotd_channel_id, timezone, schedule_time, schedule_enabled,
                       reminder_interval_minutes, created_at, updated_at
                FROM guild_settings
                WHERE guild_id = ?
                """,
                (guild_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return GuildSettings(
            guild_id=row["guild_id"],
            qotd_channel_id=row["qotd_channel_id"],
            timezone=row["timezone"],
            schedule_time=row["schedule_time"],
            schedule_enabled=bool(row["schedule_enabled"]),
            reminder_interval_minutes=row["reminder_interval_minutes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def update_qotd_channel(self, guild_id: int, channel_id: int) -> None:
        await self._update_fields(guild_id, {"qotd_channel_id": channel_id})

    async def update_schedule(
        self,
        guild_id: int,
        *,
        schedule_time: str,
        timezone: str,
        enabled: bool,
    ) -> None:
        await self._update_fields(
            guild_id,
            {
                "schedule_time": schedule_time,
                "timezone": timezone,
                "schedule_enabled": int(enabled),
            },
        )

    async def update_reminder_interval(self, guild_id: int, interval_minutes: int | None) -> None:
        await self._update_fields(guild_id, {"reminder_interval_minutes": interval_minutes})

    async def _update_fields(self, guild_id: int, fields: dict[str, object]) -> None:
        assignments = ", ".join(f"{name} = ?" for name in fields)
        params = [*fields.values(), guild_id]
        async with self.database.connection() as connection:
            await connection.execute(
                f"""
                UPDATE guild_settings
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                params,
            )
            await connection.commit()


class RoleAssignmentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def list_for_guild(self, guild_id: int) -> list[RoleAssignment]:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, role_id, purpose, created_at
                FROM role_assignments
                WHERE guild_id = ?
                ORDER BY purpose, role_id
                """,
                (guild_id,),
            )
            rows = await cursor.fetchall()

        return [
            RoleAssignment(
                id=row["id"],
                guild_id=row["guild_id"],
                role_id=row["role_id"],
                purpose=row["purpose"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def list_for_purpose(self, guild_id: int, purpose: str) -> list[RoleAssignment]:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, role_id, purpose, created_at
                FROM role_assignments
                WHERE guild_id = ? AND purpose = ?
                ORDER BY role_id
                """,
                (guild_id, purpose),
            )
            rows = await cursor.fetchall()

        return [
            RoleAssignment(
                id=row["id"],
                guild_id=row["guild_id"],
                role_id=row["role_id"],
                purpose=row["purpose"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def replace_for_purpose(self, guild_id: int, purpose: str, role_ids: list[int]) -> None:
        async with self.database.connection() as connection:
            await connection.execute(
                "DELETE FROM role_assignments WHERE guild_id = ? AND purpose = ?",
                (guild_id, purpose),
            )
            await connection.executemany(
                """
                INSERT INTO role_assignments (guild_id, role_id, purpose)
                VALUES (?, ?, ?)
                """,
                [(guild_id, role_id, purpose) for role_id in role_ids],
            )
            await connection.commit()


class QuestionDraftRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create(
        self,
        guild_id: int,
        creator_user_id: int,
        *,
        current_step: str,
        status: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> QuestionDraft:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO question_drafts (
                    guild_id, creator_user_id, current_step, status, payload_json, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    creator_user_id,
                    current_step,
                    status,
                    json.dumps(payload),
                    _isoformat(expires_at),
                ),
            )
            await connection.commit()
            draft_id = cursor.lastrowid

        draft = await self.get(draft_id)
        if draft is None:
            raise RuntimeError("Draft creation succeeded but the draft could not be reloaded")
        return draft

    async def get(self, draft_id: int) -> QuestionDraft | None:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, creator_user_id, current_step, status, payload_json,
                       expires_at, created_at, updated_at
                FROM question_drafts
                WHERE id = ?
                """,
                (draft_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return QuestionDraft(
            id=row["id"],
            guild_id=row["guild_id"],
            creator_user_id=row["creator_user_id"],
            current_step=row["current_step"],
            status=row["status"],
            payload_json=row["payload_json"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_active_for_creator(self, guild_id: int, creator_user_id: int) -> QuestionDraft | None:
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id, guild_id, creator_user_id, current_step, status, payload_json,
                       expires_at, created_at, updated_at
                FROM question_drafts
                WHERE guild_id = ?
                  AND creator_user_id = ?
                  AND status IN ('draft', 'awaiting_confirmation')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (guild_id, creator_user_id),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return QuestionDraft(
            id=row["id"],
            guild_id=row["guild_id"],
            creator_user_id=row["creator_user_id"],
            current_step=row["current_step"],
            status=row["status"],
            payload_json=row["payload_json"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def update(
        self,
        draft_id: int,
        *,
        current_step: str,
        status: str,
        payload: dict[str, object],
        expires_at: datetime,
    ) -> None:
        async with self.database.connection() as connection:
            await connection.execute(
                """
                UPDATE question_drafts
                SET current_step = ?,
                    status = ?,
                    payload_json = ?,
                    expires_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    current_step,
                    status,
                    json.dumps(payload),
                    _isoformat(expires_at),
                    draft_id,
                ),
            )
            await connection.commit()


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
        return int(row["next_position"])