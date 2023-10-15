from __future__ import annotations

import contextlib
import datetime
import json
from typing import TYPE_CHECKING

import discord
from discord import InteractionType
from discord.ext import tasks, commands


if TYPE_CHECKING:
    from core import Genji


class AnalyticsTasks(commands.Cog):
    def __init__(self, bot: Genji):
        super().__init__()
        self.bot = bot
        self.send_info_to_db.start()

    async def cog_unload(self):
        self.send_info_to_db.cancel()

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context[Genji]):
        self.bot.log_analytics(
            ctx.command.qualified_name,
            ctx.author.id,
            ctx.message.created_at,
            ctx.kwargs,
        )

    @commands.Cog.listener()
    async def on_interaction(self, itx: discord.Interaction[Genji]):
        if itx.command and itx.type == InteractionType.application_command:
            self.bot.log_analytics(
                itx.command.name, itx.user.id, itx.created_at, itx.namespace.__dict__
            )

    @tasks.loop(seconds=60)
    async def send_info_to_db(self):
        query = """
            INSERT INTO analytics (event, user_id,  date_collected, args)
            VALUES($1, $2, $3, $4)
        ;"""

        rows: list[tuple[str, int, datetime.datetime, str]] = []
        for raw_event, user_id, timestamp, args in self.bot.analytics_buffer:
            with contextlib.suppress(KeyError):
                args.pop("screenshot")
            rows.append((raw_event, user_id, timestamp, json.dumps(args)))
        if rows:
            await self.bot.database.set_many(query, rows)
            self.bot.analytics_buffer = []


async def setup(bot: Genji):
    bot.analytics_buffer = []
    await bot.add_cog(AnalyticsTasks(bot))
