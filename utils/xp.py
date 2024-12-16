from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar

from discord.utils import maybe_coroutine

if TYPE_CHECKING:
    from core import Genji
    from database import Database

P = ParamSpec("P")
R = TypeVar("R")

def safe_execution(func: Callable[P, R]) -> Callable[P, bool]:
    """Wrap a function to return a bool on its success."""
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> bool:
        try:
            _ = maybe_coroutine(func, *args, **kwargs)
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
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
            SET amount = amount + excluded.amount
        """
        await self._db.execute(query, user_id, amount)

    async def _(self):
        self.grant_user_xp(141372217677053952, 1)
