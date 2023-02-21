from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import utils
import views

if typing.TYPE_CHECKING:
    import core


class Polls(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="poll")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def start_poll(
        self,
        itx: discord.Interaction[core.Genji],
        title: str,
        option_1: str,
        option_2: str,
        option_3: str | None,
        option_4: str | None,
        option_5: str | None,
    ) -> None:
        await itx.response.defer()
        chart = await self.bot.loop.run_in_executor(
            None, views.create_graph, {"None": 100}
        )
        embed = await views.build_embed(title)
        options = self.get_default_valid_options(
            [option_1, option_2, option_3, option_4, option_5]
        )
        view = views.PollView(options, title)
        message = await itx.edit_original_response(
            embed=embed, attachments=[chart], view=view
        )
        await self.insert_poll_info(itx, options, message.id, title)

    @staticmethod
    def get_default_valid_options(options: list[str | None]) -> list[str]:
        return [option for option in options if option]

    @staticmethod
    async def insert_poll_info(
        itx: discord.Interaction[core.Genji],
        options: list[str | None],
        message_id: int,
        title: str,
    ):
        query = "INSERT INTO polls_info (user_id, options, message_id, title) VALUES ($1, $2, $3, $4)"
        await itx.client.database.set(
            query,
            itx.user.id,
            options,
            message_id,
            title,
        )


async def setup(bot: core.Genji):
    await bot.add_cog(Polls(bot))
