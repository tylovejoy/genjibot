from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

from utils import constants

if typing.TYPE_CHECKING:
    import core


class Tags(commands.GroupCog, group_name="tag"):
    @app_commands.command()
    @app_commands.checks.cooldown(3, 30, key=lambda i: (i.guild_id, i.user.id))
    async def view(
        self,
        itx: discord.Interaction[core.Genji],
        name: str,
    ) -> None:
        """View a tag."""
        await itx.response.send_message("Tags command is currently under construction.")

    @app_commands.command()
    async def create(self, itx: discord.Interaction[core.Genji]) -> None:
        """Create a tag."""
        await itx.response.send_message("Tags command is currently under construction.")


async def setup(bot: core.Genji) -> None:
    """Add cog to bot."""
    await bot.add_cog(Tags(bot), guilds=[discord.Object(id=constants.GUILD_ID)])
