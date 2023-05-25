from __future__ import annotations

import asyncio
import io
import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import utils
from cogs.info_pages.views import CompletionInfoView, MapInfoView

if typing.TYPE_CHECKING:
    import core


class InfoPage(commands.Cog):
    """Info page"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def completioninfo(
        self,
        ctx: commands.Context[core.Genji],
    ) -> None:
        await ctx.message.delete(delay=1)
        embed = utils.GenjiEmbed(
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
        embed = utils.GenjiEmbed(
            title="Map Submission / Playtest Information!",
            description="Click the buttons below to learn more!",
        )
        await ctx.send(embed=embed, view=MapInfoView())
