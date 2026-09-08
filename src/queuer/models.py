from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class GuildSettings:
    guild_id: int
    qotd_channel_id: int | None
    timezone: str
    schedule_time: str | None
    schedule_enabled: bool
    reminder_interval_minutes: int | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class RoleAssignment:
    id: int
    guild_id: int
    role_id: int
    purpose: str
    created_at: str


@dataclass(slots=True)
class DraftPayload:
    question_type: str | None = None
    prompt_text: str | None = None
    reaction_options: list[str] | None = None
    this_or_that_options: list[str] | None = None
    target_user_id: int | None = None
    embed: dict[str, Any] | None = None
    attachments: list[str] | None = None
    external_urls: list[str] | None = None


@dataclass(slots=True)
class QuestionDraft:
    id: int
    guild_id: int
    creator_user_id: int
    current_step: str
    status: str
    payload_json: str
    expires_at: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class QueueItem:
    id: int
    guild_id: int
    draft_id: int | None
    status: str
    type: str
    prompt_text: str
    payload_json: str
    target_user_id: int | None
    created_by_user_id: int
    approved_by_user_id: int | None
    approved_at: str | None
    position: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ServiceBundle:
    configuration: Any
    drafts: Any
    queue: Any


def utcnow() -> datetime:
    return datetime.utcnow()
