from __future__ import annotations

from typing import TYPE_CHECKING

from .map_edits import MapEdits
from .map_search import MapSearch
from .misc import MapsMisc
from .submission import MapSubmissions

if TYPE_CHECKING:
    import core


async def setup(bot: core.Genji):
    """Add Cog to Discord bot."""
    inst = MapSubmissions(bot)
    await bot.add_cog(inst)
    await bot.add_cog(MapSearch(bot))
    await bot.add_cog(MapsMisc(bot))

    # Add mod commands to CommanGroup (`/mod map`)
    cog = bot.get_cog("CommandGroups")
    cog.map.add_command(inst.mod_submit_map)
    edits = MapEdits(bot)
    for command in edits.walk_app_commands():
        cog.map.add_command(command)
