from __future__ import annotations

import dataclasses
import typing

import discord
from discord import app_commands

import utils

if typing.TYPE_CHECKING:
    import core


class MapNameTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_names:
            value = utils.fuzz_(value, itx.client.map_names)
        return value


class MapTypeTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_types:
            value = utils.fuzz_(value, itx.client.map_types)
        return value


class MapMechanicsTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_mechanics:
            value = utils.fuzz_(value, itx.client.map_mechanics)
        return value


class MapRestrictionsTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_restrictions:
            value = utils.fuzz_(value, itx.client.map_restrictions)
        return value


@dataclasses.dataclass
class MapSubmission:
    creator: discord.Member | utils.FakeUser
    map_code: str
    map_name: str
    checkpoint_count: int
    description: str | None
    guide_url: str | None
    medals: tuple[float, float, float] | None

    map_types: list[str] | None
    mechanics: list[str] | None
    restrictions: list[str] | None
    difficulty: str | None  # base difficulty
    creator_diffs: list[str] | None

    def __str__(self):
        return (
            f"┣ `Code` {self.map_code}\n"
            f"┣ `Map` {self.map_name}\n"
            f"┣ `Type` {', '.join(self.map_types)}\n"
            f"┣ `Checkpoints` {self.checkpoint_count}\n"
            f"┣ `Difficulty` {self.difficulty}\n"
            f"┣ `Mechanics` {', '.join(self.mechanics)}\n"
            f"┣ `Restrictions` {', '.join(self.restrictions)}\n"
            f"{self.guide_text}"
            f"{self.medals_text}"
            f"┗ `Desc` {self.description}\n"
        )

    @property
    def gold(self):
        return self.medals[0]

    @property
    def silver(self):
        return self.medals[1]

    @property
    def bronze(self):
        return self.medals[2]

    @property
    def guide_text(self):
        res = ""
        if self.guide_url:
            res = f"┣ `Guide` [Link]({self.guide_url})\n"
        return res

    @property
    def medals_text(self):
        res = ""
        if all([self.gold, self.silver, self.bronze]):
            res = (
                "┣ `Medals` "
                f"{utils.FULLY_VERIFIED_GOLD} {self.gold} | "
                f"{utils.FULLY_VERIFIED_SILVER} {self.silver} | "
                f"{utils.FULLY_VERIFIED_BRONZE} {self.bronze}\n"
            )
        return res

    def set_extras(self, **args):
        for k, v in args.items():
            setattr(self, k, v)

    async def insert_playtest(
        self,
        itx: core.Interaction[core.Genji],
        thread_id: int,
        thread_msg_id: int,
        new_map_id: int,
    ):
        await itx.client.database.set(
            """
            INSERT INTO playtest (thread_id, message_id, map_code, user_id, value, is_author, original_msg)
            VALUES ($1, $2, $3, $4, $5, $6, $7) 
            """,
            thread_id,
            thread_msg_id,
            self.map_code,
            itx.user.id,
            utils.DIFFICULTIES_RANGES[self.difficulty][0],
            True,
            new_map_id,
        )

    async def insert_maps(self, itx: core.Interaction[core.Genji], mod: bool):
        await itx.client.database.set(
            """
            INSERT INTO 
            maps (map_name, map_type, map_code, "desc", official, checkpoints) 
            VALUES ($1, $2, $3, $4, $5, $6);
            """,
            self.map_name,
            self.map_types,
            self.map_code,
            self.description,
            mod,
            self.checkpoint_count,
        )

    async def insert_mechanics(self, itx: core.Interaction[core.Genji]):
        mechanics = [(self.map_code, x) for x in self.mechanics]
        await itx.client.database.set_many(
            """
            INSERT INTO map_mechanics (map_code, mechanic) 
            VALUES ($1, $2);
            """,
            mechanics,
        )

    async def insert_restrictions(self, itx: core.Interaction[core.Genji]):
        restrictions = [(self.map_code, x) for x in self.restrictions]
        await itx.client.database.set_many(
            """
            INSERT INTO map_restrictions (map_code, restriction) 
            VALUES ($1, $2);
            """,
            restrictions,
        )

    async def insert_map_creators(self, itx: core.Interaction[core.Genji]):
        await itx.client.database.set(
            """
            INSERT INTO map_creators (map_code, user_id) 
            VALUES ($1, $2);
            """,
            self.map_code,
            self.creator.id,
        )

    async def insert_map_ratings(self, itx: core.Interaction[core.Genji]):
        await itx.client.database.set(
            """
            INSERT INTO map_ratings (map_code, user_id, difficulty) 
            VALUES ($1, $2, $3);
            """,
            self.map_code,
            self.creator.id,
            utils.DIFFICULTIES_RANGES[self.difficulty][0],
        )

    async def insert_guide(self, itx: core.Interaction[core.Genji]):
        if self.guide_url:
            await itx.client.database.set(
                """INSERT INTO guides (map_code, url) VALUES ($1, $2);""",
                self.map_code,
                self.guide_url,
            )

    async def insert_medals(self, itx: core.Interaction[core.Genji]):
        if self.medals:
            await itx.client.database.set(
                """
                INSERT INTO map_medals (gold, silver, bronze, map_code)
                VALUES ($1, $2, $3, $4);
                """,
                self.gold,
                self.silver,
                self.bronze,
                self.map_code,
            )

    async def insert_all(self, itx: core.Interaction[core.Genji], mod: bool):
        await self.insert_maps(itx, mod)
        await self.insert_mechanics(itx)
        await self.insert_restrictions(itx)
        await self.insert_map_creators(itx)
        await self.insert_guide(itx)
        await self.insert_medals(itx)
