from __future__ import annotations

import typing

import discord
from discord.ext import commands

from .utils import ticket_thread_check
from .views import CloseTicketView, TicketStart

if typing.TYPE_CHECKING:
    import core


class TicketSystem(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(CloseTicketView())

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
                "- Bugs found regarding:\n"
                "  - GenjiBot\n"
                "  - Official Genji Parkour Framework\n"
                "- Map information changes\n"
                "  - Official maps\n"
                "  - Playtest maps\n"
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
        await ctx.message.add_reaction("<:_:895727516017393665>")
        await ctx.channel.edit(archived=True, locked=True)
