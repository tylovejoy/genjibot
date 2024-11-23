from __future__ import annotations

import typing

import discord.ui

from utils import cache

if typing.TYPE_CHECKING:
    import core


def bool_string(value: bool) -> str:
    """Return ON or OFF depending on the boolean value given."""
    if value:
        return "ON"
    else:
        return "OFF"


ENABLED_EMOJI = "🔔"
DISABLED_EMOJI = "🔕"


class SettingsView(discord.ui.View):
    """User settings view."""

    def __init__(self, original_itx: discord.Interaction[core.Genji], flags: int) -> None:
        super().__init__(timeout=3600)
        self.itx = original_itx
        self.flags = cache.SettingFlags(flags)
        self.verification = NotificationButton("Verification", cache.SettingFlags.VERIFICATION in self.flags)
        self.add_item(self.verification)
        self.promotion = NotificationButton("Promotion", cache.SettingFlags.PROMOTION in self.flags)
        self.add_item(self.promotion)

    @discord.ui.button(label="Change Name", style=discord.ButtonStyle.blurple, row=1)
    async def name_change(self, itx: discord.Interaction[core.Genji], button: discord.ui.Button) -> None:
        """Change name button callback."""
        await itx.response.send_modal(NameChangeModal())


class NotificationButton(discord.ui.Button):
    """Notification settings button."""

    view: SettingsView

    def __init__(self, name: str, value: bool) -> None:
        self.name = name
        super().__init__()
        self.edit_button(name, value)

    async def callback(self, itx: discord.Interaction[core.Genji]) -> None:
        """Notification button callback."""
        await itx.response.defer(ephemeral=True)
        self.view.flags ^= getattr(cache.SettingFlags, self.name.upper())
        self.edit_button(self.name, getattr(cache.SettingFlags, self.name.upper()) in self.view.flags)
        await self.view.itx.edit_original_response(view=self.view)
        await itx.client.database.set(
            "UPDATE users SET flags = $1 WHERE user_id = $2;",
            self.view.flags,
            itx.user.id,
        )
        itx.client.cache.users[itx.user.id].flags = self.view.flags

    def edit_button(self, name: str, value: bool) -> None:
        """Edit button."""
        self.label = f"{name} Notifications are {bool_string(value)}"
        self.emoji = ENABLED_EMOJI if value else DISABLED_EMOJI
        self.style = discord.ButtonStyle.green if value else discord.ButtonStyle.red


class NameChangeModal(discord.ui.Modal, title="Change Name"):
    """Name change modal."""

    name = discord.ui.TextInput(
        label="Nickname",
        style=discord.TextStyle.short,
        placeholder="Write your most commonly known nickname/alias.",
    )

    async def on_submit(self, itx: discord.Interaction[core.Genji]) -> None:
        """Name change modal callback."""
        await itx.response.send_message(f"You have changed your display name to {self.name}!", ephemeral=True)
        itx.client.cache.users[itx.user.id].update_nickname(self.name.value)

        await itx.client.database.set(
            "UPDATE users SET nickname = $1 WHERE user_id = $2;",
            self.name.value[:25],
            itx.user.id,
        )
