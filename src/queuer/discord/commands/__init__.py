from .admin import register_admin_commands
from .qotd import register_qotd_commands
from .system import register_error_handler, register_system_commands


def register_commands(bot) -> None:
    register_system_commands(bot)
    register_admin_commands(bot)
    register_qotd_commands(bot)
    register_error_handler(bot)


__all__ = ["register_commands"]
