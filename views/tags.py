from __future__ import annotations

import typing

import discord.ui
from discord import app_commands

import views

if typing.TYPE_CHECKING:
    import core


NUMBER_EMOJI = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}

class TagFuzzView(discord.ui.View):
    def __init__(self, itx: core.Interaction[core.Genji], options: list[str]):
        super().__init__(timeout=None)
        self.itx = itx
        self.matches.options = [
            discord.SelectOption(label=x, value=x, emoji=NUMBER_EMOJI[i + 1])
            for i, x in enumerate(options)
        ]

    @discord.ui.select()
    async def matches(
        self, itx: core.Interaction[core.Genji], select: discord.SelectMenu
    ):
        await itx.response.defer()
        tag = [
            x
            async for x in itx.client.database.get(
                "SELECT * FROM tags WHERE name=$1",
                select.values[0],
            )
        ][0]

        await itx.edit_original_response(
            content=f"**{tag.name}**\n\n{tag.value}", view=None, embed=None
        )


class TagCreate(discord.ui.Modal, title="Create Tag"):
    name = discord.ui.TextInput(label="Name")
    value = discord.ui.TextInput(label="Value", style=discord.TextStyle.paragraph)

    async def on_submit(self, itx: core.Interaction[core.Genji]):

        view = views.Confirm(itx)
        await itx.response.send_message(
            content=f"Is this correct?\n\n**{self.name}**\n\n{self.value}",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return

        await itx.client.database.set(
            "INSERT INTO tags (name, value) VALUES ($1, $2);",
            self.name.value,
            self.value.value,
        )
        itx.client.tag_cache.append(self.name.value)
        itx.client.tag_choices.append(
            app_commands.Choice(name=self.name.value, value=self.name.value)
        )
