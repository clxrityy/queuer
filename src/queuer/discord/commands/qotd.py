from __future__ import annotations

import json
from typing import Any, Optional

import discord
from discord import app_commands

from ..app import QueuerBot
from ..embeds import build_snippet_embed
from .access import ensure_contributor_access


QUESTION_TYPE_CHOICES = [
    app_commands.Choice(name="Reaction poll", value="reaction"),
    app_commands.Choice(name="Written response", value="written_response"),
    app_commands.Choice(name="This or that", value="this_or_that"),
]


def parse_options(raw_options: Optional[str]) -> list[str]:
    if raw_options is None:
        return []

    normalized = raw_options.replace("\n", "|").replace(",", "|")
    return [option.strip() for option in normalized.split("|") if option.strip()]


def build_draft_summary(payload: dict[str, Any]) -> str:
    lines = [
        f"Type: {payload.get('question_type') or 'unset'}",
        f"Prompt: {payload.get('prompt_text') or 'unset'}",
    ]

    reaction_options = payload.get("reaction_options") or []
    if reaction_options:
        lines.append("Reaction options: " + ", ".join(str(option) for option in reaction_options))

    this_or_that_options = payload.get("this_or_that_options") or []
    if this_or_that_options:
        lines.append("This or that options: " + " vs ".join(str(option) for option in this_or_that_options))

    target_user_id = payload.get("target_user_id")
    if target_user_id is not None:
        lines.append(f"Target user: <@{target_user_id}>")
    else:
        lines.append("Target user: automatic selection later")

    return "\n".join(lines)


def build_draft_embed(*, draft_id: int, payload: dict[str, Any]) -> discord.Embed:
    return build_snippet_embed(
        title=f"QOTD Draft #{draft_id}",
        description="Review the draft, then run `/qotd-confirm` to enqueue it.",
        snippet=build_draft_summary(payload),
        language="text",
        color=discord.Color.gold(),
        render_as_code_block=False,
        field_name="Details",
    )


def register_qotd_commands(bot: QueuerBot) -> None:
    @bot.tree.command(name="qotd-draft", description="Create or replace your active QOTD draft.")
    @app_commands.guild_only()
    @app_commands.describe(
        question_type="Choose the type of question to queue.",
        prompt="The question that will be asked.",
        options="Use |, comma, or new lines between options. Required for reaction and this-or-that.",
        target_user="Optional member to target for the question.",
    )
    @app_commands.choices(question_type=QUESTION_TYPE_CHOICES)
    async def qotd_draft(
        interaction: discord.Interaction,
        question_type: app_commands.Choice[str],
        prompt: str,
        options: Optional[str] = None,
        target_user: Optional[discord.Member] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_contributor_access(bot, interaction)

        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise app_commands.AppCommandError("Prompt cannot be empty.")

        parsed_options = parse_options(options)
        payload_patch: dict[str, object] = {
            "question_type": question_type.value,
            "prompt_text": cleaned_prompt,
            "reaction_options": None,
            "this_or_that_options": None,
            "target_user_id": target_user.id if target_user is not None else None,
        }

        if question_type.value == "reaction":
            if len(parsed_options) < 2:
                raise app_commands.AppCommandError("Reaction questions require at least 2 options.")
            payload_patch["reaction_options"] = parsed_options
        elif question_type.value == "this_or_that":
            if len(parsed_options) != 2:
                raise app_commands.AppCommandError("This-or-that questions require exactly 2 options.")
            payload_patch["this_or_that_options"] = parsed_options
        elif parsed_options:
            raise app_commands.AppCommandError("Written response questions do not accept options.")

        draft = await bot.services.drafts.begin_or_resume(bot.config.guild_id, interaction.user.id)
        draft = await bot.services.drafts.save_progress(
            draft.id,
            current_step="confirm",
            status="awaiting_confirmation",
            payload_patch=payload_patch,
        )

        payload = json.loads(draft.payload_json)
        await interaction.followup.send(
            embed=build_draft_embed(draft_id=draft.id, payload=payload),
            ephemeral=True,
        )

    @bot.tree.command(name="qotd-confirm", description="Confirm your active QOTD draft and enqueue it.")
    @app_commands.guild_only()
    async def qotd_confirm(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_contributor_access(bot, interaction)

        draft = await bot.services.drafts.get_active(bot.config.guild_id, interaction.user.id)
        if draft is None:
            raise app_commands.AppCommandError("You do not have an active QOTD draft to confirm.")

        queue_item = await bot.services.queue.confirm_draft(draft.id, interaction.user.id)
        payload = json.loads(queue_item.payload_json)
        embed = build_snippet_embed(
            title=f"Queued QOTD #{queue_item.id}",
            description=f"Your question has been queued in position {queue_item.position}.",
            snippet=build_draft_summary(payload),
            language="text",
            color=discord.Color.green(),
            render_as_code_block=False,
            field_name="Details",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
