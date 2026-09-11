from __future__ import annotations

from ..db import Database
from ..models import GuildSettings


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

    async def update_qotd_channel(self, guild_id: int, channel_id: int | None) -> None:
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
