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
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot
        log.info("Start- Updating global names...")
        self._update_global_names.start()
        # self._playtest_auto_approve.start()
        # self._playtest_expiration_warning.start()
        # self._playtest_expiration.start()

    @tasks.loop(hours=1)
    async def _update_global_names(self) -> None:
        await self.bot.wait_until_ready()
        global_names = [(u.id, u.name) for u in self.bot.users if u.global_name is not None]
        query = """
            INSERT INTO user_global_names (user_id, global_name)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
            SET global_name = excluded.global_name
            WHERE user_global_names.global_name != excluded.global_name
        """
        log.debug("Updating global names...")
        await self.bot.database.executemany(query, global_names)

    @tasks.loop(time=[datetime.time(0, 0, 0), datetime.time(12, 0, 0)])
    async def _playtest_auto_approve(self) -> None:
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
    async def _playtest_expiration(self) -> None:
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
    async def _playtest_expiration_warning(self) -> None:
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
        rows = await self.bot.database.fetch(query)
        async for row in rows:
            assert guild
            creator = guild.get_member(row["user_id"])
            if not creator:
                continue
            message = (
                f"Hey there, {creator.mention}!\n\n"
                f"Friendly reminder that your map **{row['map_code']}** will be scheduled for deletion in "
                f"**1 week** since there are no votes.\n"
            )
            thread = guild.get_thread(row["thread_id"])
            if thread:
                await thread.send(message)
            map_codes.append((row["map_code"],))
        await self.bot.database.executemany(
            "UPDATE map_submission_dates SET alerted = TRUE WHERE map_code = $1",
            map_codes,
        )


async def setup(bot: core.Genji) -> None:
    """Add cog to bot."""
    await bot.add_cog(Tasks(bot))
