from __future__ import annotations

import unittest

from queuer.discord.qotd_delivery import (
    build_queue_post_content,
    get_cycle_candidate_member_ids,
    parse_reaction_options,
)


class QotdDeliveryTests(unittest.TestCase):
    def test_parse_reaction_options_accepts_custom_emoji_tokens_without_pipe_separators(self) -> None:
        parsed = parse_reaction_options("<:yes:111> <:no:222>, <a:maybe:333>\n<:later:444>")

        self.assertEqual(["<:yes:111>", "<:no:222>", "<a:maybe:333>", "<:later:444>"], parsed)

    def test_parse_reaction_options_rejects_non_emoji_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "custom Discord emoji tokens"):
            parse_reaction_options("Yes <:yes:111> No <:no:222>")

    def test_cycle_candidate_member_ids_avoids_members_already_seen_in_current_cycle(self) -> None:
        candidates = get_cycle_candidate_member_ids([10, 20, 30], [30, 20])

        self.assertEqual([10], candidates)

    def test_cycle_candidate_member_ids_resets_after_everyone_has_been_seen(self) -> None:
        candidates = get_cycle_candidate_member_ids([10, 20, 30], [30, 20, 10])

        self.assertEqual([10, 20, 30], candidates)

    def test_build_queue_post_content_mentions_alert_roles_and_omits_reaction_options(self) -> None:
        content = build_queue_post_content(
            "What are we shipping next?",
            {
                "reaction_options": ["<:yes:111>", "<:no:222>"],
                "this_or_that_options": None,
            },
            alert_role_ids=[1234],
        )

        self.assertEqual("<@&1234>\nWhat are we shipping next?", content)


if __name__ == "__main__":
    unittest.main()
