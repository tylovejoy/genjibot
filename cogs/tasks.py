from __future__ import annotations

import typing

from discord.ext import commands, tasks

if typing.TYPE_CHECKING:
    import core


class Tasks(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot
        self.cache.start()

    @tasks.loop(hours=24, count=1)
    async def cache(self):
        maps = [
            x
            async for x in self.bot.database.get(
                """
                SELECT m.map_code, array_agg(mc.user_id) as user_ids, archived
                FROM maps m
                         LEFT JOIN map_creators mc on m.map_code = mc.map_code
                GROUP BY m.map_code;
                """,
            )
        ]
        users = [
            x
            async for x in self.bot.database.get(
                """
                SELECT
                    user_id,
                    nickname,
                    flags,
                    user_id in (
                        SELECT DISTINCT user_id FROM map_creators
                    ) as is_creator
                FROM users;
                """,
            )
        ]
        map_names = [
            x
            async for x in self.bot.database.get(
                """SELECT name as value FROM all_map_names ORDER BY 1""",
            )
        ]

        map_types = [
            x
            async for x in self.bot.database.get(
                """SELECT name as value FROM all_map_types ORDER BY order_num""",
            )
        ]
        map_mechanics = [
            x
            async for x in self.bot.database.get(
                """SELECT name as value FROM all_map_mechanics ORDER BY order_num""",
            )
        ]
        map_restrictions = [
            x
            async for x in self.bot.database.get(
                """SELECT name as value FROM all_map_restrictions ORDER BY order_num""",
            )
        ]
        tags = [
            x
            async for x in self.bot.database.get(
                """SELECT name as value FROM tags ORDER BY 1""",
            )
        ]

        self.bot.cache.setup(
            users=users,
            maps=maps,
            map_names=map_names,
            map_types=map_types,
            map_mechanics=map_mechanics,
            map_restrictions=map_restrictions,
            tags=tags,
        )

    @commands.command()
    @commands.is_owner()
    async def refresh_cache(
        self,
        ctx: commands.Context[core.Genji],
    ):
        self.bot.cache.refresh_cache()
        await ctx.message.delete()


async def setup(bot: core.Genji):
    await bot.add_cog(Tasks(bot))
