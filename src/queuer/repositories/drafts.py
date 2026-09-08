from __future__ import annotations

import json
from datetime import datetime

from ..db import Database
from ..models import QuestionDraft
from ._shared import isoformat_utc


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
                    isoformat_utc(expires_at),
                ),
            )
            await connection.commit()
            draft_id = cursor.lastrowid

        if draft_id is None:
            raise RuntimeError("Draft creation succeeded but no draft ID was returned")

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
                                    AND expires_at > CURRENT_TIMESTAMP
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
                    isoformat_utc(expires_at),
                    draft_id,
                ),
            )
            await connection.commit()
