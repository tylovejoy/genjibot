from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from cogs.tickets.utils import TICKET_CHANNEL

if TYPE_CHECKING:
    import core


class TicketStart(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        ...

    @discord.ui.button(
        label="Click me to get help from a Sensei!",
        custom_id="create_ticket",
        style=discord.ButtonStyle.grey,
        emoji="🆘",
    )
    async def create_ticket(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        await itx.response.send_modal(TicketStartModal())


class TicketStartModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(
            title="Create Ticket",
            timeout=3600,
        )

    feedback = discord.ui.TextInput(
        label="Issue",
        style=discord.TextStyle.long,
        placeholder="Describe your issue here",
        required=True,
        max_length=500,
    )

    async def on_submit(self, itx: discord.Interaction[core.Genji]):
        await itx.response.send_message(f"Creating ticket...", ephemeral=True)
        channel: discord.TextChannel = itx.client.get_channel(TICKET_CHANNEL)
        thread = await channel.create_thread(
            name=f"{itx.user.display_name[20:]}",
            message=None,
            type=None,
            invitable=False,
        )
        await thread.add_user(itx.user)
        await thread.send(content=self.feedback.value)

    async def on_error(
        self, itx: discord.Interaction[core.Genji], error: Exception
    ) -> None:
        await itx.response.send_message("Oops! Something went wrong.", ephemeral=True)
