from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta
from typing import Optional

from ..models import DraftPayload, QuestionDraft, utcnow
from ..repositories import QuestionDraftRepository


class DraftService:
    def __init__(self, draft_repository: QuestionDraftRepository) -> None:
        self.draft_repository = draft_repository

    async def get_active(self, guild_id: int, creator_user_id: int) -> Optional[QuestionDraft]:
        return await self.draft_repository.get_active_for_creator(guild_id, creator_user_id)

    async def begin_or_resume(self, guild_id: int, creator_user_id: int, *, ttl_minutes: int = 60) -> QuestionDraft:
        draft = await self.draft_repository.get_active_for_creator(guild_id, creator_user_id)
        if draft is not None:
            return draft

        expires_at = utcnow() + timedelta(minutes=ttl_minutes)
        payload = asdict(DraftPayload())
        return await self.draft_repository.create(
            guild_id,
            creator_user_id,
            current_step="question",
            status="draft",
            payload=payload,
            expires_at=expires_at,
        )

    async def save_progress(
        self,
        draft_id: int,
        *,
        current_step: str,
        payload_patch: dict[str, object],
        status: str = "draft",
        ttl_minutes: int = 60,
    ) -> QuestionDraft:
        draft = await self.draft_repository.get(draft_id)
        if draft is None:
            raise ValueError(f"Unknown draft id: {draft_id}")

        payload = json.loads(draft.payload_json)
        payload.update(payload_patch)
        expires_at = utcnow() + timedelta(minutes=ttl_minutes)
        await self.draft_repository.update(
            draft_id,
            current_step=current_step,
            status=status,
            payload=payload,
            expires_at=expires_at,
        )

        updated = await self.draft_repository.get(draft_id)
        if updated is None:
            raise RuntimeError("Draft update succeeded but the draft could not be reloaded")
        return updated

    async def mark_awaiting_confirmation(self, draft_id: int, *, ttl_minutes: int = 60) -> QuestionDraft:
        return await self.save_progress(
            draft_id,
            current_step="confirm",
            status="awaiting_confirmation",
            payload_patch={},
            ttl_minutes=ttl_minutes,
        )
