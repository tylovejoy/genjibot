from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Awaitable, Callable, ParamSpec, TypeVar

import msgspec
from discord.utils import maybe_coroutine

if TYPE_CHECKING:
    from core import Genji
    from database import Database

    P = ParamSpec("P")
    R = TypeVar("R")


log = logging.getLogger(__name__)


def safe_execution(func: Callable[P, R]) -> Callable[P, Awaitable[bool]]:
    """Wrap a function to return a bool on its success."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> bool:
        try:
            await maybe_coroutine(func, *args, **kwargs)
            return True
        except Exception as _:
            log.error("An error occurred during the execution of %s:", func.__name__, exc_info=True)
            return False

    return wrapper


class XP:
    def __init__(self, bot: Genji) -> None:
        self._bot: Genji = bot
        self._db: Database = bot.database

    @safe_execution
    async def grant_user_xp(self, user_id: int, amount: int) -> None:
        query = """
            INSERT INTO xptable (user_id, amount) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
            SET amount = xptable.amount + excluded.amount
        """
        await self._db.execute(query, user_id, amount)

    async def _(self, user_id: int) -> None:
        success = await self.grant_user_xp(user_id, 1)
        if success:
            log.info("Successfully granted xp for user: %s", "nebula")
        else:
            log.info("Failed to grant xp for user: %s", "nebula")
