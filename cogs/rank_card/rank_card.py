from __future__ import annotations

import asyncio
import io
import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import utils
from cogs.rank_card.utils import RANKS, RankCardBuilder
from utils import rank_finder

if typing.TYPE_CHECKING:
    import core


class RankCard(commands.Cog):
    """Rank Card"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="rank-card")
    @app_commands.guilds(
        discord.Object(id=utils.GUILD_ID), discord.Object(id=968951072599187476)
    )
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def rank_card(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[
            discord.Member | utils.FakeUser, utils.AllUserTransformer
        ]
        | None,
    ) -> None:
        await itx.response.defer(ephemeral=True)
        if not user or user.id == itx.user.id:
            user = itx.user

        totals = await self._get_map_totals()
        completions = await utils.get_completions_data(
            itx.client, user.id, include_beginner=True
        )
        world_records = await self._get_world_record_count(user.id)
        maps = await self._get_maps_count(user.id)
        playtests = await self._get_playtests_count(user.id)
        rank_num, _, _, _ = await rank_finder(itx.client, user)
        rank = RANKS[rank_num - 1]
        background = await self._get_background_choice(user.id)
        data = {
            "rank": rank,
            "name": itx.client.cache.users[user.id].nickname,
            "bg": background,
            "maps": maps,
            "playtests": playtests,
            "world_records": world_records,
        }
        for category, values in completions.items():
            data[category] = {
                "completed": values[0],
                "gold": values[1],
                "silver": values[2],
                "bronze": values[3],
            }
        for total in totals:
            if total.name not in data:
                data[total.name] = {
                    "completed": 0,
                    "gold": 0,
                    "silver": 0,
                    "bronze": 0,
                }
            data[total.name]["total"] = total.total

        image = await asyncio.to_thread(RankCardBuilder(data).create_card)
        with io.BytesIO() as image_binary:
            image.save(image_binary, "PNG")
            image_binary.seek(0)

            await itx.edit_original_response(
                content="",
                attachments=[discord.File(fp=image_binary, filename="rank_card.png")],
            )

    async def _get_map_totals(self):
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

        return [x async for x in self.bot.database.get(query)]

    async def _get_world_record_count(self, user_id: int):
        query = """
            WITH all_records AS (SELECT 
                user_id, r.map_code, record, rank() OVER (PARTITION BY r.map_code ORDER BY record) as pos
            
            
            FROM records r
            LEFT JOIN maps m on r.map_code = m.map_code
            WHERE m.official = TRUE AND record < 99999999 AND video IS NOT NULL)
            SELECT count(*) FROM all_records WHERE user_id = $1 AND pos = 1
        
        """
        row = await self.bot.database.get_row(query, user_id)
        return row.count

    async def _get_maps_count(self, user_id: int):
        query = """
            SELECT count(*) FROM maps LEFT JOIN map_creators mc on maps.map_code = mc.map_code WHERE user_id = $1 AND official=TRUE
        """
        row = await self.bot.database.get_row(query, user_id)
        return row.count

    async def _get_playtests_count(self, user_id):
        query = "SELECT amount FROM playtest_count WHERE user_id = $1"
        row = await self.bot.database.get_row(query, user_id)
        if not row:
            return 0
        return row.amount

    async def _get_background_choice(self, user_id: int):
        query = "SELECT value FROM background WHERE user_id = $1"
        row = await self.bot.database.get_row(query, user_id)
        if not row:
            return 1
        return row.value
