from __future__ import annotations

import dataclasses

import discord
from discord import app_commands

import core
import database
import utils


class MapNameTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_names:
            value = utils.fuzz_(value, itx.client.cache.map_names.list)
        return value


class MapTypeTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_types:
            value = utils.fuzz_(value, itx.client.cache.map_types.list)
        return value


class MapMechanicsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_mechanics.list:
            value = utils.fuzz_(value, itx.client.cache.map_mechanics.list)
        return value


class MapRestrictionsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_restrictions.list:
            value = utils.fuzz_(value, itx.client.cache.map_restrictions.list)
        return value


class MapSubmissionDBMixin:
    async def insert_playtest(
        self,
        itx: discord.Interaction[core.Genji],
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

    async def insert_maps(self, itx: discord.Interaction[core.Genji], mod: bool):
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

    async def insert_mechanics(self, itx: discord.Interaction[core.Genji]):
        mechanics = [(self.map_code, x) for x in self.mechanics]
        await itx.client.database.set_many(
            """
            INSERT INTO map_mechanics (map_code, mechanic) 
            VALUES ($1, $2);
            """,
            mechanics,
        )

    async def insert_restrictions(self, itx: discord.Interaction[core.Genji]):
        restrictions = [(self.map_code, x) for x in self.restrictions]
        await itx.client.database.set_many(
            """
            INSERT INTO map_restrictions (map_code, restriction) 
            VALUES ($1, $2);
            """,
            restrictions,
        )

    async def insert_map_creators(self, itx: discord.Interaction[core.Genji]):
        await itx.client.database.set(
            """
            INSERT INTO map_creators (map_code, user_id) 
            VALUES ($1, $2);
            """,
            self.map_code,
            self.creator.id,
        )

    async def insert_map_ratings(self, itx: discord.Interaction[core.Genji]):
        await itx.client.database.set(
            """
            INSERT INTO map_ratings (map_code, user_id, difficulty) 
            VALUES ($1, $2, $3);
            """,
            self.map_code,
            self.creator.id,
            utils.DIFFICULTIES_RANGES[self.difficulty][0],
        )

    async def insert_guide(self, itx: discord.Interaction[core.Genji]):
        _guides = [(self.map_code, guide) for guide in self.guides if guide]
        if _guides:
            await itx.client.database.set_many(
                """INSERT INTO guides (map_code, url) VALUES ($1, $2);""",
                _guides,
            )

    async def insert_medals(self, itx: discord.Interaction[core.Genji]):
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

    async def insert_timestamp(self, itx: discord.Interaction[core.Genji], mod: bool):
        if not mod:
            await itx.client.database.set(
                """
                INSERT INTO map_submission_dates (user_id, map_code)
                VALUES ($1, $2);
                """,
                self.creator.id,
                self.map_code,
            )

    async def insert_all(self, itx: discord.Interaction[core.Genji], mod: bool):
        await self.insert_maps(itx, mod)
        await self.insert_mechanics(itx)
        await self.insert_restrictions(itx)
        await self.insert_map_creators(itx)
        await self.insert_map_ratings(itx)
        await self.insert_guide(itx)
        await self.insert_medals(itx)
        await self.insert_timestamp(itx, mod)


@dataclasses.dataclass
class BaseMapData:
    creator: discord.Member | utils.FakeUser
    map_code: str
    map_name: str
    checkpoint_count: int
    description: str | None
    medals: tuple[float, float, float] | None
    guides: list[str] | None = None
    map_types: list[str] | None = None
    mechanics: list[str] | None = None
    restrictions: list[str] | None = None
    difficulty: str | None = None  # base difficulty
    quality: float | None = None

    @property
    def gold(self):
        return self.medals[0]

    @property
    def silver(self):
        return self.medals[1]

    @property
    def bronze(self):
        return self.medals[2]

    def to_dict(self) -> dict[str, str]:
        return {
            "Code": self.map_code,
            "Map": self.map_name,
            "Type": self.map_types,
            "Checkpoints": self.checkpoint_count,
            "Difficulty": self.difficulty,
            "Mechanics": self.mechanics,
            "Restrictions": self.restrictions,
            "Guide": self.guides,
            "Medals": self.medals,
            "Desc": self.description,
        }


class MapSubmission(BaseMapData, MapSubmissionDBMixin):
    ...


async def get_map_info(
    client: core.Genji, message_id: int | None = None
) -> list[database.DotRecord | None]:
    return [
        x
        async for x in client.database.get(
            """
            SELECT map_name,
                   map_type,
                   m.map_code,
                   "desc",
                   official,
                   archived,
                   AVG(value) as value,
                   array_agg(DISTINCT url)              AS guide,
                   array_agg(DISTINCT mech.mechanic)    AS mechanics,
                   array_agg(DISTINCT rest.restriction) AS restrictions,
                   checkpoints,
                   array_agg(DISTINCT mc.user_id)       AS creator_ids,
                   gold,
                   silver,
                   bronze,
                   p.message_id
            FROM playtest p
                     LEFT JOIN maps m on m.map_code = p.map_code
                     LEFT JOIN map_mechanics mech on mech.map_code = m.map_code
                     LEFT JOIN map_restrictions rest on rest.map_code = m.map_code
                     LEFT JOIN map_creators mc on m.map_code = mc.map_code
                     LEFT JOIN users u on mc.user_id = u.user_id
                     LEFT JOIN guides g on m.map_code = g.map_code
                     LEFT JOIN map_medals mm on m.map_code = mm.map_code
            WHERE is_author = TRUE AND ($1::bigint IS NULL OR $1::bigint = p.message_id)
            GROUP BY checkpoints, map_name,
                     m.map_code, "desc", official, map_type, gold, silver, bronze, archived, p.message_id
            """,
            message_id,
        )
    ]
