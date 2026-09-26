from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from ..models import GuildSettings
from ..repositories import GuildSettingsRepository, RoleAssignmentRepository
from ..scheduling import normalize_schedule_time, validate_timezone_name


ROLE_PURPOSE_ADMIN = "admin"
ROLE_PURPOSE_CONTRIBUTOR = "contributor"
ROLE_PURPOSE_ELIGIBLE = "eligible"
ROLE_PURPOSE_ALERT = "alert"


class ConfigurationService:
    def __init__(
        self,
        settings_repository: GuildSettingsRepository,
        role_repository: RoleAssignmentRepository,
    ) -> None:
        self.settings_repository = settings_repository
        self.role_repository = role_repository

    async def get_snapshot(self, guild_id: int) -> dict[str, object]:
        settings = await self.settings_repository.get(guild_id)
        roles = await self.role_repository.list_for_guild(guild_id)
        roles_by_purpose: dict[str, list[int]] = {}
        for role in roles:
            roles_by_purpose.setdefault(role.purpose, []).append(role.role_id)

        return {
            "settings": asdict(settings) if settings is not None else None,
            "roles": roles_by_purpose,
        }

    async def get_settings(self, guild_id: int) -> Optional[GuildSettings]:
        return await self.settings_repository.get(guild_id)

    async def set_qotd_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        await self.settings_repository.update_qotd_channel(guild_id, channel_id)

    async def set_schedule(self, guild_id: int, schedule_time: str, timezone: str, enabled: bool) -> None:
        normalized_time = normalize_schedule_time(schedule_time)
        validated_timezone = validate_timezone_name(timezone)
        await self.settings_repository.update_schedule(
            guild_id,
            schedule_time=normalized_time,
            timezone=validated_timezone,
            enabled=enabled,
        )

    async def disable_schedule(self, guild_id: int) -> None:
        settings = await self.settings_repository.get(guild_id)
        if settings is None:
            raise ValueError(f"Unknown guild id: {guild_id}")
        schedule_time = settings.schedule_time or "09:00"
        await self.settings_repository.update_schedule(
            guild_id,
            schedule_time=normalize_schedule_time(schedule_time),
            timezone=validate_timezone_name(settings.timezone),
            enabled=False,
        )

    async def set_reminder_interval(self, guild_id: int, interval_minutes: Optional[int]) -> None:
        await self.settings_repository.update_reminder_interval(guild_id, interval_minutes)

    async def replace_admin_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ADMIN, role_ids)

    async def replace_contributor_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_CONTRIBUTOR, role_ids)

    async def replace_eligible_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ELIGIBLE, role_ids)

    async def replace_alert_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ALERT, role_ids)
