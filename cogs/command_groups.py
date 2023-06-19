from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from utils import GUILD_ID


if TYPE_CHECKING:
    import core


mod_commands = app_commands.Group(
    name="mod",
    guild_ids=[GUILD_ID, 868981788968640554],
    description="Mod only commands",
)


map_commands = app_commands.Group(
    name="map",
    guild_ids=[GUILD_ID, 868981788968640554],
    description="Mod only commands",
    parent=mod_commands,
)


class CommandGroups(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot

    mod = mod_commands
    map = map_commands


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(CommandGroups(bot))
