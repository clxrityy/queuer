from __future__ import annotations

from ..db import Database
from ..models import RoleAssignment


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