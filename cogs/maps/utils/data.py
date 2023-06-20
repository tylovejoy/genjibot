import dataclasses
from collections import namedtuple

import discord

from utils import utils


class Medals(namedtuple("Medals", ["gold", "silver", "bronze"])):
    __slots__ = ()

    def __str__(self):
        return (
            (
                f"`Medals` "
                f"{utils.FULLY_VERIFIED_GOLD} {self.gold} | "
                f"{utils.FULLY_VERIFIED_SILVER} {self.silver} | "
                f"{utils.FULLY_VERIFIED_BRONZE} {self.bronze}"
            )
            if all((self.gold, self.silver, self.bronze))
            else ""
        )


@dataclasses.dataclass
class BaseMapData:
    creators: list[discord.Member | discord.User | utils.FakeUser]
    map_code: str
    map_name: str
    checkpoint_count: int
    description: str | None
    medals: Medals | None
    guides: list[str] | None = None
    map_types: list[str] | None = None
    mechanics: list[str] | None = None
    restrictions: list[str] | None = None
    difficulty: int | None = None  # base difficulty
    quality: float | None = None
