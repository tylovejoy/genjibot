from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core import Genji


async def setup(bot: Genji) -> None:
    """Add cog to bot."""
