from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Optional

from .embeds import truncate_snippet


CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:[A-Za-z0-9_]{2,32}:\d+>")


def parse_text_options(raw_options: Optional[str]) -> list[str]:
    if raw_options is None:
        return []

    normalized = raw_options.replace("\n", "|").replace(",", "|")
    return [option.strip() for option in normalized.split("|") if option.strip()]


def parse_reaction_options(raw_options: Optional[str]) -> list[str]:
    if raw_options is None or not raw_options.strip():
        return []

    reaction_options = CUSTOM_EMOJI_PATTERN.findall(raw_options)
    remaining_text = CUSTOM_EMOJI_PATTERN.sub(" ", raw_options)
    normalized_remaining_text = (
        remaining_text.replace("\n", " ").replace(",", " ").replace("|", " ").strip()
    )
    if normalized_remaining_text:
        raise ValueError(
            "Reaction questions only accept custom Discord emoji tokens like <:name:123456789012345678>."
        )
    return reaction_options


def dedupe_preserving_order(values: Iterable[str]) -> list[str]:
    deduped_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        if value in seen_values:
            continue
        seen_values.add(value)
        deduped_values.append(value)
    return deduped_values


def get_cycle_candidate_member_ids(
    eligible_member_ids: Sequence[int],
    recent_selected_user_ids: Sequence[int],
) -> list[int]:
    if not eligible_member_ids:
        return []

    recent_unique_user_ids: list[int] = []
    eligible_member_id_set = set(eligible_member_ids)
    for user_id in recent_selected_user_ids:
        if user_id not in eligible_member_id_set or user_id in recent_unique_user_ids:
            continue
        recent_unique_user_ids.append(user_id)
        if len(recent_unique_user_ids) >= len(eligible_member_ids):
            break

    candidate_member_ids = [user_id for user_id in eligible_member_ids if user_id not in recent_unique_user_ids]
    return candidate_member_ids or list(eligible_member_ids)


def build_queue_post_content(
    prompt_text: str,
    payload: dict[str, object],
    *,
    alert_role_ids: Optional[Sequence[int]] = None,
) -> str:
    lines: list[str] = []
    if alert_role_ids:
        role_mentions = " ".join(f"<@&{role_id}>" for role_id in alert_role_ids)
        if role_mentions:
            lines.append(role_mentions)

    lines.append(prompt_text)

    this_or_that_options = [str(option) for option in (payload.get("this_or_that_options") or [])]
    if this_or_that_options:
        lines.append(" vs ".join(this_or_that_options))

    return truncate_snippet("\n".join(line for line in lines if line), limit=1900)
