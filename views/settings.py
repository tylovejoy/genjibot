from __future__ import annotations

import enum
import typing

import discord.ui


if typing.TYPE_CHECKING:
    import core


class Settings(enum.IntFlag):
    VERIFICATION = enum.auto()
    PROMOTION = enum.auto()
    DEFAULT = VERIFICATION | PROMOTION
    NONE = 0


def bool_string(value: bool) -> str:
    if value:
        return "ON"
    else:
        return "OFF"


ENABLED_EMOJI = "🔔"
DISABLED_EMOJI = "🔕"


class SettingsView(discord.ui.View):
    def __init__(self, original_itx: core.Interaction[core.Genji], flags: int):
        super().__init__(timeout=None)
        self.itx = original_itx
        self.flags = Settings(flags)
        self.verification = NotificationButton(
            "Verification", Settings.VERIFICATION in self.flags
        )
        self.add_item(self.verification)
        self.promotion = NotificationButton(
            "Promotion", Settings.PROMOTION in self.flags
        )
        self.add_item(self.promotion)

    @discord.ui.button(label="Change Name", style=discord.ButtonStyle.blurple, row=1)
    async def name_change(
        self, itx: core.Interaction[core.Genji], button: discord.ui.Button
    ):
        await itx.response.send_modal(NameChangeModal())


class NotificationButton(discord.ui.Button):
    view: SettingsView

    def __init__(self, name: str, value: bool):
        self.name = name
        super().__init__()
        self.edit_button(name, value)

    async def callback(self, itx: core.Interaction[core.Genji]):
        await itx.response.defer(ephemeral=True)
        self.view.flags ^= getattr(Settings, self.name.upper())
        self.edit_button(
            self.name, getattr(Settings, self.name.upper()) in self.view.flags
        )
        await self.view.itx.edit_original_response(view=self.view)
        await itx.client.database.set(
            "UPDATE users SET flags = $1 WHERE user_id = $2;",
            self.view.flags,
            itx.user.id,
        )
        itx.client.all_users[itx.user.id]["flags"] = self.view.flags

    def edit_button(self, name: str, value: bool):
        self.label = f"{name} Notifications are {bool_string(value)}"
        self.emoji = ENABLED_EMOJI if value else DISABLED_EMOJI
        self.style = discord.ButtonStyle.green if value else discord.ButtonStyle.red


class NameChangeModal(discord.ui.Modal, title="Change Name"):
    name = discord.ui.TextInput(
        label="Nickname",
        style=discord.TextStyle.short,
        placeholder="Write your most commonly known nickname/alias.",
    )

    async def on_submit(self, itx: core.Interaction[core.Genji]):
        await itx.response.send_message(
            f"You have changed your display name to {self.name}!", ephemeral=True
        )
        itx.client.all_users[itx.user.id]["nickname"] = self.name.value
        await itx.client.database.set(
            "UPDATE users SET nickname = $1 WHERE user_id = $2;",
            self.name.value[:25],
            itx.user.id,
        )
