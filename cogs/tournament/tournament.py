from __future__ import annotations

from typing import TYPE_CHECKING

import discord.utils
from discord.ext import commands

if TYPE_CHECKING:
    from core import Genji


class TournamentSetup(commands.Cog):
    def __init__(self, bot: Genji):
        self.bot = bot

    @commands.command()
    async def start(self, ctx: commands.Context):
        announcements = await ctx.channel.create_thread(name="Announcements - Tournament Name")
        chat = await ctx.channel.create_thread(name="Chat - Tournament Name")
        submissions = await ctx.channel.create_thread(name="Submissions - Tournament Name")
        now = discord.utils.utcnow()
        now_formatted = discord.utils.format_dt(now, style="F")
        await ctx.send(
            f"# Tournament Name | {now_formatted}\n"
            f"- {announcements.jump_url}\n"
            f"- {chat.jump_url}\n"
            f"- {submissions.jump_url}"
        )
