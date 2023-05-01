from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import database
import utils
import views
from utils import wrap_string_with_percent

if typing.TYPE_CHECKING:
    import core


class RankCard(commands.Cog):
    """Rank Card"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="rank-card")
    @app_commands.guilds(
        discord.Object(id=utils.GUILD_ID), discord.Object(id=968951072599187476)
    )
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def rank_card(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[str, utils.UserTransformer] | None,
    ) -> None:
        ...
