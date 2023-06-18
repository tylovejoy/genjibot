from __future__ import annotations

import typing

import discord
from discord.ext import commands

from cogs.tickets.utils import ticket_thread_check
from cogs.tickets.views import TicketStart

if typing.TYPE_CHECKING:
    import core


class TicketSystem(commands.Cog):
    """Ticket System"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def setup_tickets(
        self,
        ctx: commands.Context[core.Genji],
    ) -> None:
        await ctx.channel.send(
            content=(
                "# Do you require assistance from a Sensei?\n"
                "### Press the button below for any of the following: \n"
                "- Map changes\n"
                "- Playtest issues\n"
                "- Other users\n"
                "- Sensitive information\n\n"
                "## **Using this system will create a private thread only Senseis can see.**"
            ),
            view=TicketStart(),
        )

    @commands.command()
    @ticket_thread_check()
    async def solved(
        self,
        ctx: commands.Context[core.Genji],
    ) -> None:
        assert isinstance(ctx.channel, discord.Thread)
        await ctx.channel.edit(archived=True, locked=True)
