from __future__ import annotations

import logging
import os
import typing

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

import cogs
import views
from utils import constants, embeds, errors, models, ranks, records, utils

if typing.TYPE_CHECKING:
    import core

PR_FILTERS = typing.Literal["All", "World Records", "Completions", "Records"]
LB_FILTERS = typing.Literal["All", "Fully Verified", "Verified", "Completions"]

log = logging.getLogger(__name__)


class Records(commands.Cog):
    """Records"""

    def __init__(self, bot: core.Genji):
        self.bot = bot
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="personal-records",
                callback=self.pr_context_callback,
                guild_ids=[constants.GUILD_ID],
            )
        )
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="world-records",
                callback=self.wr_context_callback,
                guild_ids=[constants.GUILD_ID],
            )
        )
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="completions",
                callback=self.completion_context_callback,
                guild_ids=[constants.GUILD_ID],
            )
        )

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def summary(
        self,
        itx: discord.Interaction[core.Genji],
        user: (app_commands.Transform[int | discord.Member | utils.FakeUser, records.AllUserTransformer] | None) = None,
    ):
        """Display a summary of your records and associated difficulties/medals

        Args:
            itx: Interaction
            user: User

        """
        await itx.response.defer(ephemeral=True)
        if not user:
            user = itx.user

        if isinstance(user, discord.Member) or isinstance(user, utils.FakeUser):
            user = user.id
        else:
            user = int(user)

        rows = await utils.fetch_user_rank_data(itx.client.database, user, True, False)
        description = ""
        for row in rows:
            description += (
                f"```{row.difficulty}```"
                f"` Total` {row.completions}\n"
                f"`  Gold` {row.gold} {constants.FULLY_VERIFIED_GOLD}\n"
                f"`Silver` {row.silver} {constants.FULLY_VERIFIED_SILVER}\n"
                f"`Bronze` {row.bronze} {constants.FULLY_VERIFIED_BRONZE}\n\n"
            )

        embed = embeds.GenjiEmbed(
            title="Summary",
            description=description,
        )
        await itx.edit_original_response(embed=embed)

    async def _check_map_exists(self, map_code: str) -> bool:
        query = "SELECT EXISTS(SELECT map_code FROM maps WHERE map_code = $1);"
        return await self.bot.database.fetchval(query, map_code)

    async def _check_map_archived(self, map_code: str) -> bool:
        query = "SELECT archived FROM maps WHERE map_code = $1;"
        return await self.bot.database.fetchval(query, map_code)

    async def _check_if_creator(self, map_code: str, user_id: int) -> bool:
        query = "SELECT EXISTS(SELECT 1 FROM map_creators WHERE map_code = $1 AND user_id = $2);"
        return await self.bot.database.fetchval(query, map_code, user_id)

    async def _fetch_record(self, map_code: str, user_id: int) -> models.Record | None:
        query = """
            WITH user_records_for_map AS (
                SELECT
                    r.map_code,
                    record,
                    screenshot,
                    video,
                    verified,
                    m.map_name,
                RANK() OVER (ORDER BY record) AS latest
                FROM records r LEFT JOIN maps m on r.map_code = m.map_code
                WHERE r.map_code=$1 AND user_id=$2 AND verified
            )
            SELECT * FROM user_records_for_map WHERE latest=1
        """
        row = await self.bot.database.fetchrow(query, map_code, user_id)
        if not row:
            return
        return models.Record(**row)

    async def _fetch_difficulty(self, map_code: str) -> float:
        query = "SELECT avg(difficulty) FROM map_ratings WHERE map_code = $1 AND verified = TRUE"
        return await self.bot.database.fetchval(query, map_code)

    @staticmethod
    async def _start_overwrite_view(itx: discord.Interaction[core.Genji]) -> bool:
        overwrite_view = views.RecordVideoConfirmCompletion(itx)
        await itx.edit_original_response(
            content=(
                f"{itx.user.mention}, your last submission was fully verified, "
                f"are you sure you want to overwrite your last record "
                f"with one that can only be partially verified?"
            ),
            view=overwrite_view,
        )
        await overwrite_view.wait()
        return overwrite_view.value

    async def _compare_submission_to_last_record(
        self,
        itx: discord.Interaction[core.Genji],
        old_record: models.Record,
        submission: models.Record,
    ):
        if old_record.video:
            if submission.record >= old_record.record:
                raise errors.RecordNotFasterError
            if submission.record < old_record.record and not submission.video:
                value = await self._start_overwrite_view(itx)
                if not value:
                    return
        if submission.record >= old_record.record and not submission.video:
            raise errors.RecordNotFasterError
        return True

    async def _upload_screenshot(self, screenshot: discord.Attachment) -> str:
        image = await screenshot.read()

        r = await self.bot.session.post(
            "http://genji-lust:8000/v1/images/genji-parkour-images",
            params={"format": screenshot.content_type.split("/")[1]},
            headers={
                "content-length": str(len(image)),
                "content-type": "application/octet-stream",
            },
            data=image,
        )
        r.raise_for_status()
        data = await r.json()
        bucket_id = data["bucket_id"]
        sizing_id = data["images"][0]["sizing_id"]
        image_id = data["image_id"]
        return f"https://cdn.bkan0n.com/{bucket_id}/{sizing_id}/{image_id}.png"

    @app_commands.command(name="submit-completion")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    @app_commands.choices(
        quality=[
            app_commands.Choice(
                name=constants.ALL_STARS[x - 1],
                value=x,
            )
            for x in range(1, 7)
        ]
    )
    async def submit_record(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeRecordsTransformer],
        screenshot: discord.Attachment,
        time: app_commands.Transform[float, records.RecordTransformer],
        quality: app_commands.Choice[int],
        video: app_commands.Transform[str, records.URLTransformer] | None,
    ) -> None:
        """Submit a record to the database. Video proof is required for full verification!

        Args:
            itx: Interaction
            map_code: Overwatch share code
            time: Time in seconds/milliseconds
            screenshot: Screenshot of completion
            video: Video of play through. REQUIRED FOR FULL VERIFICATION!
            quality: Quality of the map

        """
        await itx.response.defer(ephemeral=True)

        if itx.channel_id != constants.RECORDS:
            raise errors.WrongCompletionChannel

        if not await self._check_map_exists(map_code):
            raise errors.InvalidMapCodeError

        if await self._check_map_archived(map_code):
            raise errors.ArchivedMap

        if video and not time:
            raise errors.VideoNoRecord

        completion = False
        if not time or not await self._check_playtest(map_code):
            completion = True

        is_creator = await self._check_if_creator(map_code, itx.user.id)

        if int(os.environ["GLOBAL_MULTI_BAN"]) == 1:
            await self._check_for_global_multi_ban(map_code)

        nickname = await self.bot.database.fetch_nickname(itx.user.id)

        cdn_screenshot = await self._upload_screenshot(screenshot)

        submission = models.Record(
            map_code=map_code,
            nickname=nickname,
            user_id=itx.user.id,
            record=time,
            screenshot=cdn_screenshot,
            difficulty=await self._fetch_difficulty(map_code),
            completion=completion,
        )
        old_record = await self._fetch_record(map_code, itx.user.id)

        extra_content = ""
        if completion and video:
            extra_content = (
                "\n\n**You are submitting a video with a completion. The video will be removed automatically. "
                "If you wish to use you video as a guide please use the `/guide add` command instead.**"
            )
            video = None

        if old_record:
            _continue = await self._compare_submission_to_last_record(itx, old_record, submission)
            if not _continue:
                return

        view = views.ConfirmCompletion(
            itx,
            f"{constants.TIME}\n",
        )

        embed = models.Record.build_embed(submission, strategy=models.RecordSubmissionStrategy())
        embed.set_author(name=nickname, icon_url=itx.user.display_avatar.url)
        embed.set_image(url=cdn_screenshot)

        await itx.edit_original_response(
            content=f"{itx.user.mention}, is this correct? (Quality: {quality.name if not is_creator else 'N/A'}) {extra_content}",
            embed=embed,
            view=view,
        )
        await view.wait()
        if not view.value:
            return

        channel_msg = await itx.followup.send(
            content=f"{constants.TIME} Waiting for verification...\n",
            embed=embed,
        )

        v_view = views.VerificationView()
        verification_msg = await itx.client.get_channel(constants.VERIFICATION_QUEUE).send(
            content="**ALERT:** VIDEO SUBMISSION" if video else None,
            embed=embed,
        )

        await verification_msg.edit(view=v_view)
        async with self.bot.database.pool.acquire() as conn, conn.transaction():
            try:
                await self._insert_record_data(
                    map_code,
                    itx.user.id,
                    time,
                    channel_msg.jump_url,
                    video,
                    channel_msg.id,
                    channel_msg.channel.id,
                    verification_msg.id,
                    completion,
                    connection=conn,
                )
                await self._insert_map_rating(
                    map_code,
                    itx.user.id,
                    quality.value if not is_creator else None,
                    connection=conn,
                )
            except Exception as e:
                await itx.followup.send("There was an error while submitting your time. Please try again later.")
                await channel_msg.delete()
                await verification_msg.delete()
                raise e

    @staticmethod
    async def _insert_map_rating(
        map_code: str,
        user_id: int,
        quality: int | None,
        *,
        connection: asyncpg.Connection,
    ) -> None:
        query = """
            INSERT INTO map_ratings (user_id, map_code, quality) 
            VALUES ($1, $2, $3) 
            ON CONFLICT (user_id, map_code) DO UPDATE SET quality=excluded.quality;
        """
        await connection.execute(query, user_id, map_code, quality)

    @staticmethod
    async def _insert_record_data(
        map_code: str,
        user_id: int,
        time: float,
        screenshot: str,
        video: str,
        message_id: int,
        channel_id: int,
        verification_id: int,
        completion: bool,
        *,
        connection: asyncpg.Connection,
    ):
        query = """
            INSERT INTO records 
            (map_code, user_id, record, screenshot,
            video, verified, message_id, channel_id, hidden_id, completion) 
            VALUES ($1, $2, $3, $4, $5, FALSE, $6, $7, $8, $9)
        """
        await connection.execute(
            query,
            map_code,
            user_id,
            time,
            screenshot,
            video,
            message_id,
            channel_id,
            verification_id,
            completion,
        )

    async def _check_for_global_multi_ban(self, map_code):
        query = "SELECT EXISTS(SELECT restriction FROM map_restrictions WHERE map_code = $1 AND restriction = 'Multi Climb')"
        check = await self.bot.database.get_row(query, map_code)
        if not check.get("exists", True):
            raise errors.TemporaryMultiBan

    async def _check_playtest(self, map_code: str):
        query = "SELECT official FROM maps WHERE map_code = $1"
        return await self.bot.database.fetchval(query, map_code)

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def legacy_completions(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeRecordsTransformer],
    ) -> None:
        await itx.response.defer(ephemeral=True)
        if not await self._check_map_exists(map_code):
            raise errors.InvalidMapCodeError

        query = """
                SELECT u.nickname, 
                       record, 
                       screenshot,
                       video, 
                       lr.map_code,
                       lr.channel_id,
                       lr.message_id,
                       m.map_name,
                       medal,
                       AVG(difficulty) AS difficulty
                FROM legacy_records lr
                    LEFT JOIN users u ON lr.user_id = u.user_id
                    LEFT JOIN maps m ON m.map_code = lr.map_code
                    LEFT JOIN map_ratings mr ON m.map_code = mr.map_code
                WHERE lr.map_code = $1 AND mr.verified
                GROUP BY u.nickname, record, screenshot, video, lr.map_code, lr.channel_id, lr.message_id, m.map_name, medal
                ORDER BY record;
                """
        rows = await self.bot.database.fetch(query, map_code)
        _records = [models.Record(**r) for r in rows]

        if not _records:
            raise errors.NoRecordsFoundError

        _embeds = models.Record.build_embeds(
            _records,
            strategy=models.CompletionLeaderboardStrategy(
                map_code=map_code,
                difficulty=_records[0].difficulty_string,
                legacy=True,
            ),
        )

        view = views.Paginator(_embeds, itx.user)
        await view.start(itx)

    async def _fetch_leaderboard_records(
        self,
        *,
        map_code: str | None = None,
        user_id: int | None = None,
        lb_filters: LB_FILTERS = "All",
        pr_filters: PR_FILTERS = "All",
    ) -> list[models.Record]:
        if map_code and user_id:
            raise ValueError("Map code and user_id cannot be specified together.")
        query = """
            WITH map_creators_agg AS (
                SELECT mc.map_code, array_agg(DISTINCT u.nickname) AS creators
                FROM map_creators mc
                LEFT JOIN users u ON mc.user_id = u.user_id
                GROUP BY mc.map_code
            ),
            map_records AS (
                SELECT
                    u.nickname,
                    r.user_id,
                    record,
                    screenshot,
                    video,
                    r.map_code,
                    r.channel_id,
                    r.message_id,
                    m.map_name,
                    avg(difficulty) as difficulty,
                    rank() OVER (
                        PARTITION BY r.map_code, r.user_id
                        ORDER BY r.inserted_at DESC
                    ) AS latest,
                    gold,
                    silver,
                    bronze,
                    r.verified,
                    completion,
                    creators
                    FROM records r
                        LEFT JOIN users u ON r.user_id = u.user_id
                        LEFT JOIN maps m ON m.map_code = r.map_code
                        LEFT JOIN map_ratings mr ON m.map_code = mr.map_code
                        LEFT JOIN map_medals mm ON m.map_code = mm.map_code
                        LEFT JOIN map_creators_agg mca ON mca.map_code = m.map_code
                    WHERE mr.verified AND r.verified AND ($1::text IS NULL OR $1::text = r.map_code)
                    GROUP BY u.nickname, record, screenshot, video, r.map_code,
                        r.channel_id, r.message_id, m.map_name, gold, silver,
                        bronze, inserted_at, r.user_id, r.verified, completion, r.user_id, creators
            ), ranked_records AS (
                SELECT
                    *,
                    RANK() OVER (PARTITION BY map_code ORDER BY record) as rank_num
                FROM map_records
                WHERE map_records.latest = 1 AND (
                    $1::text IS NULL OR (
                        ($2::text != 'Fully Verified' OR (NOT completion AND video IS NOT NULL))
                    AND ($2::text != 'Verified' OR (NOT completion AND NOT video IS NOT NULL))
                    AND ($2::text != 'Completions' OR (completion))
                    )
                )
                ORDER BY difficulty, map_code
            )
            SELECT * FROM ranked_records 
            WHERE $3::bigint IS NULL OR (
                user_id=$3::bigint
                    AND ($4::text != 'World Records' OR rank_num = 1 AND NOT completion AND video IS NOT NULL)
                    AND ($4::text != 'Records' OR NOT completion)
                    AND ($4::text != 'Completions' OR completion)
            )
        """
        _records = await self.bot.database.fetch(query, map_code, lb_filters, user_id, pr_filters)
        recs = [models.Record(**r) for r in _records]
        if not recs:
            raise errors.NoRecordsFoundError
        return recs

    @app_commands.command(name="completions")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def view_records(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeRecordsTransformer],
        filters: LB_FILTERS = "All",
    ) -> None:
        """View leaderboard/completions for any map in the database.
        You are able to filter by Fully Verified, Verified, Completions or All.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            filters: Type of submissions to show

        """
        await itx.response.defer(ephemeral=True)
        if not await self._check_map_exists(map_code):
            raise errors.InvalidMapCodeError

        _records = await self._fetch_leaderboard_records(map_code=map_code, lb_filters=filters)

        _embeds = models.Record.build_embeds(
            _records,
            strategy=models.CompletionLeaderboardStrategy(
                map_code=map_code,
                difficulty=_records[0].difficulty_string,
            ),
        )

        view = views.Paginator(_embeds, itx.user)
        await view.start(itx)

    @app_commands.command(name="personal-records")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def personal_records_slash(
        self,
        itx: discord.Interaction[core.Genji],
        user: (app_commands.Transform[int | discord.Member | utils.FakeUser, records.AllUserTransformer] | None) = None,
        filters: PR_FILTERS = "All",
    ):
        """Show all records a specific user has (fully AND partially verified)

        Args:
            itx: Interaction
            user: User
            filters: Filter submissions by All, World Records, Completions, or Records

        """
        await self._personal_records(itx, user, filters)

    async def pr_context_callback(self, itx: discord.Interaction[core.Genji], user: discord.Member):
        await self._personal_records(itx, user, "Records")

    async def wr_context_callback(self, itx: discord.Interaction[core.Genji], user: discord.Member):
        await self._personal_records(itx, user, "World Records")

    async def completion_context_callback(self, itx: discord.Interaction[core.Genji], user: discord.Member):
        await self._personal_records(itx, user, "Completions")

    async def _personal_records(
        self,
        itx: discord.Interaction[core.Genji],
        user: discord.Member | str,
        filters: typing.Literal["All", "World Records", "Completions", "Records"],
    ):
        await itx.response.defer(ephemeral=True)
        if not user:
            user = itx.user

        if isinstance(user, discord.Member) or isinstance(user, utils.FakeUser):
            user_id = user.id
        else:
            user_id = int(user)

        nickname = await self.bot.database.fetch_nickname(user_id)
        _records = await self._fetch_leaderboard_records(user_id=user_id, pr_filters=filters)
        _embeds = models.Record.build_embeds(
            _records,
            strategy=models.PersonalRecordStrategy(
                user_nickname=nickname,
                filter_type=filters,
            ),
        )
        for embed in _embeds:
            embed.add_field(
                name="Legend",
                value=(
                    f"{constants.PARTIAL_VERIFIED} Completion\n"
                    f"{constants.FULLY_VERIFIED} Verified\n"
                    f"{constants.NON_MEDAL_WR} No Medal w/ World Record\n\n"
                    f"{constants.FULLY_VERIFIED_BRONZE} Bronze Medal\n"
                    f"{constants.BRONZE_WR} Bronze Medal w/ World Record\n\n"
                    f"{constants.FULLY_VERIFIED_SILVER} Silver Medal\n"
                    f"{constants.SILVER_WR} Silver Medal w/ World Record\n\n"
                    f"{constants.FULLY_VERIFIED_GOLD} Gold Medal\n"
                    f"{constants.GOLD_WR} Gold Medal w/ World Record\n"
                ),
            )

        view = views.Paginator(_embeds, itx.user)
        await view.start(itx)


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(Records(bot))
