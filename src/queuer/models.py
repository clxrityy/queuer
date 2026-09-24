from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**DATACLASS_KWARGS)
class GuildSettings:
    guild_id: int
    qotd_channel_id: Optional[int]
    timezone: str
    schedule_time: Optional[str]
    schedule_enabled: bool
    reminder_interval_minutes: Optional[int]
    created_at: str
    updated_at: str


@dataclass(**DATACLASS_KWARGS)
class RoleAssignment:
    id: int
    guild_id: int
    role_id: int
    purpose: str
    created_at: str


@dataclass(**DATACLASS_KWARGS)
class DraftPayload:
    question_type: Optional[str] = None
    prompt_text: Optional[str] = None
    reaction_options: Optional[list[str]] = None
    this_or_that_options: Optional[list[str]] = None
    target_user_id: Optional[int] = None
    embed: Optional[dict[str, Any]] = None
    attachments: Optional[list[str]] = None
    external_urls: Optional[list[str]] = None


@dataclass(**DATACLASS_KWARGS)
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


@dataclass(**DATACLASS_KWARGS)
class QueueItem:
    id: int
    guild_id: int
    draft_id: Optional[int]
    status: str
    type: str
    prompt_text: str
    payload_json: str
    target_user_id: Optional[int]
    created_by_user_id: int
    approved_by_user_id: Optional[int]
    approved_at: Optional[str]
    position: int
    created_at: str
    updated_at: str


@dataclass(**DATACLASS_KWARGS)
class ServiceBundle:
    configuration: Any
    drafts: Any
    queue: Any


def utcnow() -> datetime:
    return datetime.utcnow()
