from __future__ import annotations

import typing

import discord.ui

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
    """Tag fuzzy search view."""

    def __init__(self, itx: discord.Interaction[core.Genji], options: list[str]) -> None:
        super().__init__(timeout=3600)
        self.itx = itx
        self.matches.options = [
            discord.SelectOption(label=x, value=x, emoji=NUMBER_EMOJI[i + 1]) for i, x in enumerate(options)
        ]

    @discord.ui.select()
    async def matches(self, itx: discord.Interaction[core.Genji], select: discord.SelectMenu) -> None:
        """Select menu for tag fuzzy matches."""
        await itx.response.defer()
        tag = next(
            x
            async for x in itx.client.database.get(
                "SELECT * FROM tags WHERE name=$1",
                select.values[0],
            )
        )

        await itx.edit_original_response(content=f"**{tag.name}**\n\n{tag.value}", view=None, embed=None)


class TagCreate(discord.ui.Modal, title="Create Tag"):
    """Create tag modal."""

    name = discord.ui.TextInput(label="Name")
    value = discord.ui.TextInput(label="Value", style=discord.TextStyle.paragraph)

    async def on_submit(self, itx: discord.Interaction[core.Genji]) -> None:
        """Create tag modal callback."""
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
