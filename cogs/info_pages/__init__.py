from __future__ import annotations

import typing

from cogs.info_pages.info_page import InfoPage

if typing.TYPE_CHECKING:
    import core


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(InfoPage(bot))
