from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .utils import TICKET_CHANNEL, MODMAIL_ROLE
from utils import STAFF

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
        modal = TicketStartModal()
        await itx.response.send_modal(modal)
        await modal.wait()


class TicketStartModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(
            title="Create Ticket",
            timeout=3600,
        )

    subject = discord.ui.TextInput(
        label="Subject",
        style=discord.TextStyle.short,
        placeholder="You will be able to share more info later.",
        required=True,
        max_length=100,
    )

    async def on_submit(self, itx: discord.Interaction[core.Genji]):
        if self.subject.value is None:
            return

        await itx.response.send_message(content=f"Creating ticket...", ephemeral=True)
        channel: discord.TextChannel = itx.client.get_channel(TICKET_CHANNEL)
        thread = await channel.create_thread(
            name=f"{itx.user.display_name[:10]} | {self.subject.value[:80]}",
            message=None,
            type=None,
            invitable=False,
        )
        await thread.add_user(itx.user)
        await thread.send(
            content=(
                f"{itx.user.mention}\n"
                f"# {self.subject.value}\n"
                "Please describe your issue here.\n"
                "Be sure to include any images or other details.\n\n"
                "### If the issue is resolved, please use `?solved` to close the ticket\n\n"
                "`------------------`\n"
                f"{itx.guild.get_role(MODMAIL_ROLE).mention}"
            ),
            view=CloseTicketView(),
        )

    async def on_error(
        self, itx: discord.Interaction[core.Genji], error: Exception
    ) -> None:
        if itx.response.is_done():
            ...
        else:
            await itx.response.send_message(
                "Oops! Something went wrong.", ephemeral=True
            )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket"
    )
    async def close_ticket(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        assert isinstance(itx.channel, discord.Thread)
        await itx.channel.edit(locked=True, archived=True)
