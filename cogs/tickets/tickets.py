from __future__ import annotations

import typing

from discord.ext import commands

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
        await ctx.channel.send(view=TicketStart())
