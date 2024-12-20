from __future__ import annotations

from discord.ext import commands
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    import core


class XPCog(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot


async def setup(bot: core.Genji) -> None:
    """Add cog to bot."""
    await bot.add_cog(XPCog(bot))
