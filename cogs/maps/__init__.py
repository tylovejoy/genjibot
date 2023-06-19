from __future__ import annotations

from typing import TYPE_CHECKING

from cogs.maps.map_search import MapSearch
from cogs.maps.misc import MapsMisc
from cogs.maps.submission import MapSubmissions

if TYPE_CHECKING:
    import core


async def setup(bot: core.Genji):
    """Add Cog to Discord bot."""
    await bot.add_cog(MapSubmissions(bot))
    await bot.add_cog(MapSearch(bot))
    await bot.add_cog(MapsMisc(bot))
