from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands, tasks

import utils.utils

if typing.TYPE_CHECKING:
    import core


class Tasks(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot
        self.cache_all_users.start()
        self.cache_map_code_choices.start()
        self.cache_map_names.start()
        self.cache_map_types.start()
        self.cache_map_data.start()
        self.cache_tags.start()
        self.cache_map_mechanics.start()
        self.cache_map_restrictions.start()

    @commands.Cog.listener()
    async def on_code_cache_refresh(self):
        self.cache_map_code_choices.restart()

    @commands.command()
    @commands.is_owner()
    async def refresh_cache(
        self,
        ctx: commands.Context[core.Genji],
    ):
        self.cache_all_users.restart()
        self.cache_map_code_choices.restart()
        self.cache_map_names.restart()
        self.cache_map_types.restart()
        self.cache_map_data.restart()
        self.cache_tags.restart()
        self.cache_map_mechanics.restart()
        self.cache_map_restrictions.restart()
        await ctx.message.delete()

    @tasks.loop(hours=24, count=1)
    async def cache_map_code_choices(self):
        self.bot.logger.debug("Caching map codes...")
        self.bot.map_codes_choices = [
            app_commands.Choice(name=x.map_code, value=x.map_code)
            async for x in self.bot.database.get(
                "SELECT map_code FROM maps ORDER BY 1;",
            )
        ]

        self.bot.logger.debug("Map codes cached.")

    @tasks.loop(hours=24, count=1)
    async def cache_map_names(self):
        self.bot.logger.debug("Caching map names...")
        self.bot.map_names_choices = [
            app_commands.Choice(name=x.name, value=x.name)
            async for x in self.bot.database.get(
                "SELECT * FROM all_map_names ORDER BY 1;",
            )
        ]
        self.bot.map_names = [x.name for x in self.bot.map_names_choices]
        self.bot.logger.debug("Map names cached.")

    @tasks.loop(hours=24, count=1)
    async def cache_map_types(self):
        self.bot.logger.debug("Caching map types...")
        self.bot.map_types_options = [
            discord.SelectOption(label=x.name, value=x.name)
            async for x in self.bot.database.get(
                "SELECT * FROM all_map_types ORDER BY order_num;",
            )
        ]
        self.bot.map_types = [x.value for x in self.bot.map_types_options]
        self.bot.map_types_choices = [
            app_commands.Choice(name=x.value, value=x.value)
            for x in self.bot.map_types_options
        ]
        self.bot.logger.debug("Map types cached.")

    @tasks.loop(hours=24, count=1)
    async def cache_map_mechanics(self):
        self.bot.logger.debug("Caching map mechanics...")

        self.bot.map_mechanics = []
        self.bot.map_mechanics_options = []
        self.bot.map_mechanics_choices = []

        async for x in self.bot.database.get(
            "SELECT * FROM all_map_mechanics ORDER BY order_num;",
        ):
            self.bot.map_mechanics.append(x.name)
            self.bot.map_mechanics_options.append(
                discord.SelectOption(label=x.name, value=x.name)
            )
            self.bot.map_mechanics_choices.append(
                app_commands.Choice(name=x.name, value=x.name)
            )
        self.bot.logger.debug("Map mechanics cached.")

    @tasks.loop(hours=24, count=1)
    async def cache_map_restrictions(self):
        self.bot.logger.debug("Caching map restrictions...")

        self.bot.map_restrictions_options = []
        self.bot.map_restrictions = []
        async for x in self.bot.database.get(
            "SELECT * FROM all_map_restrictions ORDER BY order_num;",
        ):
            self.bot.map_restrictions.append(x.name)
            self.bot.map_restrictions_options.append(
                discord.SelectOption(label=x.name, value=x.name)
            )
        self.bot.logger.debug("Map restrictions cached.")

    @tasks.loop(hours=24, count=1)
    async def cache_map_data(self):
        async for x in self.bot.database.get(
            """
            SELECT DISTINCT 
                            m.map_code,
                            m.archived,
                            array_agg(distinct user_id) as user_ids
            FROM maps m
                     LEFT JOIN map_creators mc ON m.map_code = mc.map_code
            GROUP BY m.map_code
            """
        ):
            self.bot.map_cache[x.map_code] = utils.utils.MapCacheData(
                user_ids=[y for y in x.user_ids],
                archived=x.archived,
            )

    @tasks.loop(hours=24, count=1)
    async def cache_all_users(self):
        self.bot.users_choices = []
        async for x in self.bot.database.get(
            """
                SELECT u.user_id, u.nickname, u.alertable, map_code IS NOT NULL is_creator
                FROM users u
                         LEFT JOIN map_creators mc on u.user_id = mc.user_id
                GROUP BY u.user_id, nickname, alertable, is_creator;
                """
        ):
            user_data = utils.UserCacheData(
                nickname=x.nickname,
                alertable=x.alertable if x.user_id >= 1000000 else False,
            )
            choice = app_commands.Choice(name=x.nickname, value=str(x.user_id))
            self.bot.all_users[x.user_id] = user_data
            self.bot.users_choices.append(choice)

            if x.is_creator:
                self.bot.creators[
                    x.user_id
                ] = user_data
                self.bot.creators_choices.append(choice)
            # if x.user_id < 1000000:
            #     self.bot.fake_users[x.user_id] = user_data
            #     self.bot.fake_users_choices.append(choice)

    @tasks.loop(hours=24, count=1)
    async def cache_tags(self):
        self.bot.tag_cache = []
        self.bot.tag_choices = []
        async for x in self.bot.database.get("SELECT * FROM tags;"):
            self.bot.tag_cache.append(x.name)
            self.bot.tag_choices.append(app_commands.Choice(name=x.name, value=x.name))


async def setup(bot: core.Doom):
    await bot.add_cog(Tasks(bot))
