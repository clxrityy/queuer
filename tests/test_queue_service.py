from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from queuer.db import Database
from queuer.repositories import GuildSettingsRepository, QuestionDraftRepository, QueueRepository
from queuer.services.queue import QueueService


class QueueServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_remove_queued_item_deletes_target_and_reorders_remaining_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "queuer.sqlite3")
            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                await connection.execute(
                    """
                    INSERT INTO queue_items (
                        guild_id, draft_id, status, type, prompt_text, payload_json,
                        scheduled_for, target_user_id, created_by_user_id,
                        approved_by_user_id, approved_at, position
                    )
                    VALUES
                        (1, NULL, 'queued', 'written_response', 'First item', '{}', NULL, NULL, 1, 1, CURRENT_TIMESTAMP, 1),
                        (1, NULL, 'queued', 'written_response', 'Second item', '{}', NULL, NULL, 1, 1, CURRENT_TIMESTAMP, 2),
                        (1, NULL, 'queued', 'written_response', 'Third item', '{}', NULL, NULL, 1, 1, CURRENT_TIMESTAMP, 3)
                    """
                )
                await connection.commit()

            service = QueueService(
                QueueRepository(database),
                QuestionDraftRepository(database),
                GuildSettingsRepository(database),
            )

            removed_item = await service.remove_queued_item(1, 2)
            remaining_items = await service.list_queued(1)

            self.assertEqual("Second item", removed_item.prompt_text)
            self.assertEqual([1, 3], [item.id for item in remaining_items])
            self.assertEqual([1, 2], [item.position for item in remaining_items])

    async def test_remove_queued_item_rejects_non_queued_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "queuer.sqlite3")
            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                await connection.execute(
                    """
                    INSERT INTO queue_items (
                        guild_id, draft_id, status, type, prompt_text, payload_json,
                        scheduled_for, target_user_id, created_by_user_id,
                        approved_by_user_id, approved_at, position
                    )
                    VALUES
                        (1, NULL, 'sent', 'written_response', 'Already sent', '{}', NULL, NULL, 1, 1, CURRENT_TIMESTAMP, 1)
                    """
                )
                await connection.commit()

            service = QueueService(
                QueueRepository(database),
                QuestionDraftRepository(database),
                GuildSettingsRepository(database),
            )

            with self.assertRaisesRegex(ValueError, "no longer queued"):
                await service.remove_queued_item(1, 1)

    async def test_due_override_can_bypass_future_front_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "queuer.sqlite3")
            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                await connection.execute(
                    """
                    INSERT INTO queue_items (
                        guild_id, draft_id, status, type, prompt_text, payload_json,
                        scheduled_for, target_user_id, created_by_user_id,
                        approved_by_user_id, approved_at, position
                    )
                    VALUES
                        (1, NULL, 'queued', 'written_response', 'Front item', '{}', '2099-01-01T00:00:00Z', NULL, 1, 1, CURRENT_TIMESTAMP, 1),
                        (1, NULL, 'queued', 'written_response', 'Later item', '{}', '2000-01-01T00:00:00Z', NULL, 1, 1, CURRENT_TIMESTAMP, 2)
                    """
                )
                await connection.commit()

            service = QueueService(
                QueueRepository(database),
                QuestionDraftRepository(database),
                GuildSettingsRepository(database),
            )

            due_item = await service.get_due_queue_item(1, default_timezone="UTC")
            self.assertIsNotNone(due_item)
            self.assertEqual("Later item", due_item.prompt_text)

    async def test_due_override_can_bypass_front_item_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "queuer.sqlite3")
            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                await connection.execute(
                    """
                    UPDATE guild_settings
                    SET schedule_time = '23:59', schedule_enabled = 1
                    WHERE guild_id = 1
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO queue_items (
                        guild_id, draft_id, status, type, prompt_text, payload_json,
                        scheduled_for, target_user_id, created_by_user_id,
                        approved_by_user_id, approved_at, position
                    )
                    VALUES
                        (1, NULL, 'queued', 'written_response', 'Front item', '{}', NULL, NULL, 1, 1, CURRENT_TIMESTAMP, 1),
                        (1, NULL, 'queued', 'written_response', 'Override item', '{}', '2000-01-01T00:00:00Z', NULL, 1, 1, CURRENT_TIMESTAMP, 2)
                    """
                )
                await connection.commit()

            service = QueueService(
                QueueRepository(database),
                QuestionDraftRepository(database),
                GuildSettingsRepository(database),
            )

            due_item = await service.get_due_queue_item(1, default_timezone="UTC")

            self.assertIsNotNone(due_item)
            self.assertEqual("Override item", due_item.prompt_text)

    async def test_get_due_queue_item_tolerates_legacy_malformed_scheduled_for(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "queuer.sqlite3")
            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                await connection.execute(
                    """
                    INSERT INTO queue_items (
                        guild_id, draft_id, status, type, prompt_text, payload_json,
                        scheduled_for, target_user_id, created_by_user_id,
                        approved_by_user_id, approved_at, position
                    )
                    VALUES
                        (1, NULL, 'queued', 'written_response', 'Legacy item', '{}', '2000-01-01T00:00:00+00:00Z', NULL, 1, 1, CURRENT_TIMESTAMP, 1)
                    """
                )
                await connection.commit()

            service = QueueService(
                QueueRepository(database),
                QuestionDraftRepository(database),
                GuildSettingsRepository(database),
            )

            due_item = await service.get_due_queue_item(1, default_timezone="UTC")

            self.assertIsNotNone(due_item)
            self.assertEqual("Legacy item", due_item.prompt_text)

    async def test_initialize_repairs_legacy_malformed_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "queuer.sqlite3")
            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                await connection.execute(
                    """
                    INSERT INTO queue_items (
                        guild_id, draft_id, status, type, prompt_text, payload_json,
                        scheduled_for, target_user_id, created_by_user_id,
                        approved_by_user_id, approved_at, position
                    )
                    VALUES
                        (1, NULL, 'queued', 'written_response', 'Legacy item', '{}', '2000-01-01T00:00:00+00:00Z', NULL, 1, 1, CURRENT_TIMESTAMP, 1)
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO send_events (
                        guild_id, queue_item_id, status, sent_at
                    )
                    VALUES (1, 1, 'sent', '2000-01-01T00:00:00+00:00Z')
                    """
                )
                await connection.commit()

            await database.initialize(guild_id=1, default_timezone="UTC")

            async with database.connection() as connection:
                queue_cursor = await connection.execute(
                    "SELECT scheduled_for FROM queue_items WHERE id = 1"
                )
                queue_row = await queue_cursor.fetchone()
                send_cursor = await connection.execute(
                    "SELECT sent_at FROM send_events WHERE id = 1"
                )
                send_row = await send_cursor.fetchone()

            self.assertIsNotNone(queue_row)
            self.assertIsNotNone(send_row)
            self.assertEqual("2000-01-01T00:00:00Z", queue_row["scheduled_for"])
            self.assertEqual("2000-01-01T00:00:00Z", send_row["sent_at"])


if __name__ == "__main__":
    unittest.main()