from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from queuer.db import Database
from queuer.repositories import GuildSettingsRepository, QuestionDraftRepository, QueueRepository
from queuer.services.queue import QueueService


class QueueServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_later_override_does_not_skip_front_item(self) -> None:
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
            self.assertIsNone(due_item)


if __name__ == "__main__":
    unittest.main()