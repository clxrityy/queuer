from __future__ import annotations

from ..models import ServiceBundle
from ..repositories import (
    GuildSettingsRepository,
    QuestionDraftRepository,
    QueueRepository,
    RoleAssignmentRepository,
)
from .configuration import ConfigurationService
from .drafts import DraftService
from .queue import QueueService


def build_service_bundle(
    settings_repository: GuildSettingsRepository,
    role_repository: RoleAssignmentRepository,
    draft_repository: QuestionDraftRepository,
    queue_repository: QueueRepository,
) -> ServiceBundle:
    return ServiceBundle(
        configuration=ConfigurationService(settings_repository, role_repository),
        drafts=DraftService(draft_repository),
        queue=QueueService(queue_repository, draft_repository),
    )