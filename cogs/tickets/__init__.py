from __future__ import annotations

from typing import TYPE_CHECKING

from cogs.tickets.tickets import TicketSystem

if TYPE_CHECKING:
    import core


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(TicketSystem(bot))
