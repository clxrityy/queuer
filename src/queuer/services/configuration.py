from __future__ import annotations

from dataclasses import asdict

from ..repositories import GuildSettingsRepository, RoleAssignmentRepository


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

    async def set_qotd_channel(self, guild_id: int, channel_id: int | None) -> None:
        await self.settings_repository.update_qotd_channel(guild_id, channel_id)

    async def set_schedule(self, guild_id: int, schedule_time: str, timezone: str, enabled: bool) -> None:
        await self.settings_repository.update_schedule(
            guild_id,
            schedule_time=schedule_time,
            timezone=timezone,
            enabled=enabled,
        )

    async def set_reminder_interval(self, guild_id: int, interval_minutes: int | None) -> None:
        await self.settings_repository.update_reminder_interval(guild_id, interval_minutes)

    async def replace_admin_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ADMIN, role_ids)

    async def replace_contributor_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_CONTRIBUTOR, role_ids)

    async def replace_eligible_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ELIGIBLE, role_ids)

    async def replace_alert_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ALERT, role_ids)
