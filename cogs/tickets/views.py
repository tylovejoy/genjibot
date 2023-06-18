from __future__ import annotations

from typing import TYPE_CHECKING

import discord


if TYPE_CHECKING:
    import core


class TicketStart(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        ...

    @discord.ui.button(
        label="Click me to get help from a Sensei!",
        custom_id="create_ticket",
        style=discord.ButtonStyle.blurple,
        emoji="🆘",
    )
    async def create_ticket(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        ...
