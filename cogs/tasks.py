from __future__ import annotations

import datetime
import logging
import typing

from discord.ext import commands, tasks

from utils import constants

if typing.TYPE_CHECKING:
    import core

log = logging.getLogger(__name__)


class Tasks(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot
        self.cache.start()
        log.info("Start- Updating global names...")
        self._update_global_names.start()
        # self._playtest_auto_approve.start()
        # self._playtest_expiration_warning.start()
        # self._playtest_expiration.start()

    @tasks.loop(hours=12)
    async def _update_global_names(self):
        await self.bot.wait_until_ready()
        global_names = [(u.id, u.name) for u in self.bot.users if u.global_name is not None]
        query = """
            INSERT INTO user_global_names (user_id, global_name) 
            VALUES ($1, $2) 
            ON CONFLICT (user_id) DO UPDATE 
            SET global_name = excluded.global_name 
            WHERE user_global_names.global_name != excluded.global_name
        """
        log.info("Updating global names...")
        await self.bot.database.executemany(query, global_names)

    @tasks.loop(time=[datetime.time(0, 0, 0), datetime.time(12, 0, 0)])
    async def _playtest_auto_approve(self):
        query = """
      WITH
        playtest_vote_counts       AS (
          SELECT count(*) - 1 AS votes, map_code
            FROM playtest
           GROUP BY map_code
        ),
        playtest_with_votes          AS (
          SELECT map_code
            FROM playtest_vote_counts
           WHERE votes > 0
        ),
        author_playtest            AS (
          SELECT map_code, user_id, thread_id, message_id
            FROM playtest
           WHERE
             is_author = TRUE AND map_code IN (
             SELECT map_code
               FROM playtest_with_votes
           )
        )
    SELECT ap.map_code, ap.user_id, thread_id, message_id
      FROM
        author_playtest ap
          LEFT JOIN map_submission_dates msd ON ap.user_id = msd.user_id AND msd.map_code = ap.map_code
     WHERE
       date < now() - INTERVAL '4 weeks' and approved = FALSE
            """
        map_codes = []
        async for row in self.bot.database.get(query):
            thread = self.bot.get_guild(constants.GUILD_ID).get_thread(row.thread_id)
            message = thread.get_partial_message(row.message_id)
            await self.bot.playtest_views[row.message_id].toggle_finalize_button(thread, message, True)
            map_codes.append((row.map_code,))
        await self.bot.database.set_many(
            "UPDATE map_submission_dates SET approved = TRUE WHERE map_code = $1",
            map_codes,
        )

    @tasks.loop(time=[datetime.time(0, 0, 0), datetime.time(12, 0, 0)])
    async def _playtest_expiration(self):
        query = """
  WITH
    playtest_vote_counts       AS (
      SELECT count(*) - 1 AS votes, map_code
        FROM playtest
       GROUP BY map_code
    ),
    playtest_no_votes          AS (
      SELECT map_code
        FROM playtest_vote_counts
       WHERE votes = 0
    ),
    author_playtest            AS (
      SELECT map_code, user_id, thread_id, message_id
        FROM playtest
       WHERE
         is_author = TRUE AND map_code IN (
         SELECT map_code
           FROM playtest_no_votes
       )
    )
SELECT ap.map_code, ap.user_id, thread_id, message_id
  FROM
    author_playtest ap
      LEFT JOIN map_submission_dates msd ON ap.user_id = msd.user_id AND msd.map_code = ap.map_code
 WHERE
   date < now() - INTERVAL '4 weeks'
        """
        async for row in self.bot.database.get(query):
            await self.bot.playtest_views[row.message_id].time_limit_deletion()
            self.bot.playtest_views.pop(row.message_id)

    @tasks.loop(time=[datetime.time(0, 0, 0), datetime.time(12, 0, 0)])
    async def _playtest_expiration_warning(self):
        query = """
          WITH
            playtest_vote_counts       AS (
              SELECT count(*) - 1 AS votes, map_code
                FROM playtest
               GROUP BY map_code
            ),
            playtest_no_votes          AS (
              SELECT map_code
                FROM playtest_vote_counts
               WHERE votes = 0
            ),
            author_playtest            AS (
              SELECT map_code, user_id, thread_id, message_id
                FROM playtest
               WHERE
                 is_author = TRUE AND map_code IN (
                 SELECT map_code
                   FROM playtest_no_votes
               )
            )
        SELECT ap.map_code, ap.user_id, thread_id, message_id
          FROM
            author_playtest ap
              LEFT JOIN map_submission_dates msd ON ap.user_id = msd.user_id AND msd.map_code = ap.map_code
         WHERE
           date < now() - INTERVAL '3 weeks' AND alerted = FALSE
            """
        guild = self.bot.get_guild(constants.GUILD_ID)
        map_codes = []
        async for row in self.bot.database.get(query):
            creator = guild.get_member(row.user_id)
            if creator:
                mention = creator.mention
            else:
                mention = self.bot.cache.users[row.user_id].nickname
            message = (
                f"Hey there, {mention}!\n\n"
                f"Friendly reminder that your map **{row.map_code}** will be scheduled for deletion in "
                f"**1 week** since there are no votes.\n"
            )
            await guild.get_thread(row.thread_id).send(message)
            map_codes.append((row.map_code,))
        await self.bot.database.set_many(
            "UPDATE map_submission_dates SET alerted = TRUE WHERE map_code = $1",
            map_codes,
        )

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
