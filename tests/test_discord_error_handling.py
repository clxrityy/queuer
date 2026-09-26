from __future__ import annotations

import unittest

from discord import app_commands

from queuer.discord.embeds import build_error_embed, format_log_snippet, is_expected_app_command_error


class DiscordErrorHandlingTests(unittest.TestCase):
    def test_plain_app_command_error_is_treated_as_expected_input_error(self) -> None:
        error = app_commands.AppCommandError("Reaction questions require at least 2 options.")

        self.assertTrue(is_expected_app_command_error(error))

        embed = build_error_embed("qotd-draft", error)

        self.assertEqual("Invalid Input", embed.title)
        self.assertEqual(1, len(embed.fields))
        self.assertEqual(
            "Reaction questions require at least 2 options.",
            embed.fields[0].value.removeprefix("```text\n").removesuffix("\n```"),
        )

    def test_check_failure_is_treated_as_expected_command_rejection(self) -> None:
        error = app_commands.CheckFailure("You are not allowed to add QOTD questions.")

        self.assertTrue(is_expected_app_command_error(error))

    def test_format_log_snippet_handles_wrapped_invoke_errors_on_python_39(self) -> None:
        class _FakeCommand:
            name = "qotd-draft"

        original = ValueError("boom")
        wrapped = app_commands.CommandInvokeError(_FakeCommand(), original)

        snippet = format_log_snippet(wrapped)

        self.assertIn("ValueError: boom", snippet)


if __name__ == "__main__":
    unittest.main()
