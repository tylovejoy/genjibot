from __future__ import annotations

import asyncio
import io
import typing

import discord
from discord import app_commands
from discord.ext import commands

from utils import constants, transformers, utils

from .utils import RankCardBuilder

if typing.TYPE_CHECKING:
    import asyncpg

    import core


class RankCard(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    @app_commands.command(name="rank-card")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID), discord.Object(id=968951072599187476))
    async def rank_card(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[discord.Member | utils.FakeUser, transformers.AllUserTransformer] | None,
    ) -> None:
        await itx.response.defer(ephemeral=True)
        if not user or user.id == itx.user.id:
            user = itx.user

        assert user

        totals = await self._get_map_totals()
        rank_data = await utils.fetch_user_rank_data(itx.client.database, user.id, True, True)

        world_records = await self._get_world_record_count(user.id)
        maps = await self._get_maps_count(user.id)
        playtests = await self._get_playtests_count(user.id)

        rank = utils.find_highest_rank(rank_data)

        background = await self._get_background_choice(user.id)

        data = {
            "rank": rank,
            "name": await self.bot.database.fetch_nickname(user.id),
            "bg": background,
            "maps": maps,
            "playtests": playtests,
            "world_records": world_records,
        }

        for row in rank_data:
            data[row.difficulty] = {
                "completed": row.completions,
                "gold": row.gold,
                "silver": row.silver,
                "bronze": row.bronze,
            }

        data["Beginner"] = {
            "completed": 0,
            "gold": 0,
            "silver": 0,
            "bronze": 0,
        }

        for total in totals:
            data[total["name"]]["total"] = total["total"]

        image = await asyncio.to_thread(RankCardBuilder(data).create_card)
        with io.BytesIO() as image_binary:
            image.save(image_binary, "PNG")
            image_binary.seek(0)

            await itx.edit_original_response(
                content="",
                attachments=[discord.File(fp=image_binary, filename="rank_card.png")],
            )

    async def _get_map_totals(self) -> list[asyncpg.Record]:
        query = """
            WITH ranges ("range", "name") AS (
                 VALUES  ('[0,0.59)'::numrange, 'Beginner'),
                         ('[0.59,2.35)'::numrange, 'Easy'),
                         ('[2.35,4.12)'::numrange, 'Medium'),
                         ('[4.12,5.88)'::numrange, 'Hard'),
                         ('[5.88,7.65)'::numrange, 'Very Hard'),
                         ('[7.65,9.41)'::numrange, 'Extreme'),
                         ('[9.41,10.0]'::numrange, 'Hell')
            ), map_data AS
            (SELECT avg(difficulty) as difficulty FROM maps m
            LEFT JOIN map_ratings mr ON m.map_code = mr.map_code WHERE m.official = TRUE
                    AND m.archived = FALSE GROUP BY m.map_code)
            SELECT name, count(name) as total FROM map_data md
            INNER JOIN ranges r ON r.range @> md.difficulty
            GROUP BY name
        """
        return await self.bot.database.fetch(query)

    async def _get_world_record_count(self, user_id: int) -> int:
        query = """
            WITH all_records AS (
                SELECT
                    user_id,
                    r.map_code,
                    record,
                    rank() OVER (
                        PARTITION BY r.map_code
                        ORDER BY record
                    ) as pos
                FROM records r
                LEFT JOIN maps m on r.map_code = m.map_code
                WHERE m.official = TRUE AND record < 99999999 AND video IS NOT NULL
            )
            SELECT count(*) FROM all_records WHERE user_id = $1 AND pos = 1
        """
        return await self.bot.database.fetchval(query, user_id)

    async def _get_maps_count(self, user_id: int) -> int:
        query = """
            SELECT count(*)
            FROM maps
            LEFT JOIN map_creators mc ON maps.map_code = mc.map_code
            WHERE user_id = $1 AND official = TRUE
        """
        return await self.bot.database.fetchval(query, user_id)

    async def _get_playtests_count(self, user_id: int) -> int:
        query = "SELECT amount FROM playtest_count WHERE user_id = $1"
        return await self.bot.database.fetchval(query, user_id) or 0

    async def _get_background_choice(self, user_id: int) -> int:
        query = "SELECT value FROM background WHERE user_id = $1"
        return await self.bot.database.fetchval(query, user_id) or 1
