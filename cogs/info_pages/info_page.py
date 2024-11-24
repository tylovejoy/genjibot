from __future__ import annotations

import typing

from discord.ext import commands

from cogs.info_pages.views import CompletionInfoView, MapInfoView
from utils import embeds

if typing.TYPE_CHECKING:
    import core


class InfoPage(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def completioninfo(
        self,
        ctx: commands.Context[core.Genji],
    ) -> None:
        await ctx.message.delete(delay=1)
        embed = embeds.GenjiEmbed(
            title="Completions Information!",
            description="Click the buttons below to learn more!",
        )
        await ctx.send(embed=embed, view=CompletionInfoView())

    @commands.command()
    @commands.is_owner()
    async def mapsubmissioninfo(
        self,
        ctx: commands.Context[core.Genji],
    ) -> None:
        await ctx.message.delete(delay=1)
        embed = embeds.GenjiEmbed(
            title="Map Submission / Playtest Information!",
            description="Click the buttons below to learn more!",
        )
        await ctx.send(embed=embed, view=MapInfoView())
