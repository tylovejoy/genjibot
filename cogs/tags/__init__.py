from __future__ import annotations

from typing import TYPE_CHECKING

from .tags import Tags

if TYPE_CHECKING:
    from core import Genji


async def setup(bot: Genji):
    await bot.add_cog(Tags(bot))
