from __future__ import annotations

from collections.abc import Collection
from typing import Optional

import discord

from ..app import QueuerBot
from ..embeds import build_snippet_embed
from ..commands.access import replace_roles_for_purpose


def build_role_update_summary(purpose: str, role_ids: Collection[int]) -> str:
    if not role_ids:
        return f"{purpose.title()} roles cleared."
    mentions = ", ".join(f"<@&{role_id}>" for role_id in sorted(role_ids))
    return f"{purpose.title()} roles set to: {mentions}"


class _RolePicker(discord.ui.Select):
    def __init__(self, roles: list[discord.Role], selected_role_ids: set[int]) -> None:
        super().__init__(
            placeholder="Choose one or more roles",
            min_values=0,
            max_values=len(roles),
            options=[
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    default=role.id in selected_role_ids,
                )
                for role in roles
            ],
            row=0,
        )
        self.role_ids = {role.id for role in roles}

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.view, RoleSelectionView):
            return

        view = self.view
        view.selected_role_ids.difference_update(self.role_ids)
        view.selected_role_ids.update(int(role_id) for role_id in self.values)
        view.refresh_picker()
        await interaction.response.edit_message(
            embed=view.build_embed("Selection updated. Press Save Roles to persist it."),
            view=view,
        )


class RoleSelectionView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: QueuerBot,
        owner_user_id: int,
        purpose: str,
        available_roles: list[discord.Role],
        current_role_ids: set[int],
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.owner_user_id = owner_user_id
        self.purpose = purpose
        self.available_roles = available_roles
        self.selected_role_ids = current_role_ids & {role.id for role in available_roles}
        self.page = 0
        self.message: Optional[discord.InteractionMessage] = None
        self.refresh_picker()

    @property
    def page_count(self) -> int:
        return max(1, (len(self.available_roles) + 24) // 25)

    def refresh_picker(self) -> None:
        for child in list(self.children):
            if isinstance(child, _RolePicker):
                self.remove_item(child)

        page_start = self.page * 25
        page_roles = self.available_roles[page_start : page_start + 25]
        self.add_item(_RolePicker(page_roles, self.selected_role_ids))
        self.previous_page.disabled = self.page == 0
        self.next_page.disabled = self.page >= self.page_count - 1

    def disable_controls(self) -> None:
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True

    def build_embed(self, description: str) -> discord.Embed:
        return build_snippet_embed(
            title="QOTD Role Picker",
            description=f"{description}\nPage {self.page + 1} of {self.page_count}.",
            snippet=build_role_update_summary(self.purpose, self.selected_role_ids),
            language="text",
            color=discord.Color.blurple(),
            render_as_code_block=False,
            field_name="Details",
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True

        await interaction.response.send_message(
            "Only the admin who opened this picker can use it.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        self.disable_controls()

        if self.message is not None:
            await self.message.edit(
                embed=self.build_embed("This role picker timed out. Run the command again to continue."),
                view=self,
            )

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=1)
    async def previous_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.page = max(0, self.page - 1)
        self.refresh_picker()
        await interaction.response.edit_message(
            embed=self.build_embed("Choose roles, then press Save Roles."),
            view=self,
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.page = min(self.page_count - 1, self.page + 1)
        self.refresh_picker()
        await interaction.response.edit_message(
            embed=self.build_embed("Choose roles, then press Save Roles."),
            view=self,
        )

    @discord.ui.button(label="Save Roles", style=discord.ButtonStyle.success, row=2)
    async def save_roles(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await replace_roles_for_purpose(
            self.bot,
            self.bot.config.guild_id,
            self.purpose,
            sorted(self.selected_role_ids),
        )

        self.disable_controls()
        button.label = "Saved"

        await interaction.response.edit_message(
            embed=self.build_embed("The selected roles were saved."),
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Clear Roles", style=discord.ButtonStyle.danger, row=2)
    async def clear_roles(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.selected_role_ids.clear()
        await replace_roles_for_purpose(
            self.bot,
            self.bot.config.guild_id,
            self.purpose,
            [],
        )

        self.disable_controls()
        button.label = "Cleared"

        await interaction.response.edit_message(
            embed=self.build_embed("The configured roles were cleared."),
            view=self,
        )
        self.stop()
