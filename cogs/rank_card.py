from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

from utils import constants, transformers, utils

if typing.TYPE_CHECKING:
    import core


class RankCard(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    @app_commands.command(name="rank-card")
    @app_commands.guilds(constants.GUILD_ID, 968951072599187476)
    async def rank_card(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[discord.Member | utils.FakeUser, transformers.AllUserTransformer] | None,
    ) -> None:
        _user = user
        if user is None:
            _user = itx.user
        assert _user
        await itx.response.send_message(f"https://api.genji.pk/v1/rank_card/{_user.id}")


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(RankCard(bot))
