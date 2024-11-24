from __future__ import annotations

from typing import TYPE_CHECKING

from cogs.rank_card.rank_card import RankCard

if TYPE_CHECKING:
    import core


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(RankCard(bot))
