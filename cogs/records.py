from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import database
import utils
import views

if typing.TYPE_CHECKING:
    import core

PR_TYPES = typing.Literal["All", "World Records", "Completions", "Records"]


class Records(commands.Cog):
    """Records"""

    def __init__(self, bot: core.Genji):
        self.bot = bot
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="personal-records",
                callback=self.pr_context_callback,
                guild_ids=[utils.GUILD_ID],
            )
        )
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="world-records",
                callback=self.wr_context_callback,
                guild_ids=[utils.GUILD_ID],
            )
        )
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="completions",
                callback=self.completion_context_callback,
                guild_ids=[utils.GUILD_ID],
            )
        )

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def summary(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[
            int | discord.Member | utils.FakeUser, utils.AllUserTransformer
        ]
        | None = None,
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

        data = await utils.get_completions_data(itx.client, user)
        description = ""
        for diff in utils.DIFFICULTIES:
            if diff not in data:
                completions, gold, silver, bronze = 0, 0, 0, 0
            else:
                completions, gold, silver, bronze = data[diff]

            description += (
                f"```{diff}```"
                f"` Total` {completions}\n"
                f"`  Gold` {gold} {utils.FULLY_VERIFIED_GOLD}\n"
                f"`Silver` {silver} {utils.FULLY_VERIFIED_SILVER}\n"
                f"`Bronze` {bronze} {utils.FULLY_VERIFIED_BRONZE}\n\n"
            )

        embed = utils.GenjiEmbed(
            title="Summary",
            description=description,
        )
        await itx.edit_original_response(embed=embed)

    @app_commands.command(name="submit-completion")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def submit_record(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
        screenshot: discord.Attachment,
        time: app_commands.Transform[float, utils.RecordTransformer],
        video: app_commands.Transform[str, utils.URLTransformer] | None,
    ) -> None:
        """
        Submit a record to the database. Video proof is required for full verification!

        Args:
            itx: Interaction
            map_code: Overwatch share code
            time: Time in seconds/milliseconds
            screenshot: Screenshot of completion
            video: Video of play through. REQUIRED FOR FULL VERIFICATION!
        """
        await itx.response.defer(ephemeral=True)

        if itx.channel_id != utils.RECORDS:
            raise utils.WrongCompletionChannel

        if map_code not in itx.client.cache.maps.keys:
            raise utils.InvalidMapCodeError

        if itx.client.cache.maps[map_code].archived is True:
            raise utils.ArchivedMap

        if video and not time:
            raise utils.VideoNoRecord

        if not time or await self.check_playtest(map_code):
            time = utils.COMPLETION_PLACEHOLDER

        search = [
            x
            async for x in itx.client.database.get(
                "SELECT record, screenshot, video, verified, m.map_name "
                "FROM records r LEFT JOIN maps m on r.map_code = m.map_code "
                "WHERE r.map_code=$1 AND user_id=$2;",
                map_code,
                itx.user.id,
            )
        ]

        if search:
            search = search[0]

            if search.video:
                if time >= search.record:
                    raise utils.RecordNotFasterError
                if time < search.record and not video:
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
                    if not overwrite_view.value:
                        return

            if not search.video and (time >= search.record) and not video:
                raise utils.RecordNotFasterError

        view = views.ConfirmCompletion(
            await utils.Roles.find_highest_rank(itx.user),
            itx,
            f"{utils.TIME}\n",
        )

        user_facing_screenshot = await screenshot.to_file(filename="image.png")

        query = """SELECT avg(difficulty) as difficulty FROM map_ratings WHERE map_code = $1"""
        row = await itx.client.database.get_row(query, map_code)
        embed = utils.record_embed(
            {
                "difficulty": row.difficulty,
                "map_code": map_code,
                "record": time,
                "video": video,
                "user_name": itx.client.cache.users[itx.user.id].nickname,
                "user_url": itx.user.display_avatar.url,
            }
        )
        user_msg = await itx.edit_original_response(
            content=f"{itx.user.mention}, is this correct?",
            embed=embed,
            view=view,
            attachments=[user_facing_screenshot],
        )
        await view.wait()
        if not view.value:
            return

        channel_screenshot = await screenshot.to_file(filename="image.png")
        channel_msg = await itx.followup.send(
            content=f"{utils.TIME} Waiting for verification...\n",
            embed=embed,
            file=channel_screenshot,
        )

        verification_screenshot = await screenshot.to_file(filename="image.png")
        verification_msg = await itx.client.get_channel(utils.VERIFICATION_QUEUE).send(
            content="**ALERT:** VIDEO SUBMISSION" if video else None,
            embed=embed,
            file=verification_screenshot,
        )

        v_view = views.VerificationView()
        await verification_msg.edit(view=v_view)
        await itx.client.database.set(
            """
            INSERT INTO records_queue 
            (map_code, user_id, record, screenshot,
            video, message_id, channel_id, hidden_id, rating) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            map_code,
            itx.user.id,
            time,
            channel_msg.jump_url,
            video,
            channel_msg.id,
            channel_msg.channel.id,
            verification_msg.id,
            None if not getattr(view, "quality", None) else int(view.quality.values[0]),
        )
        await user_msg.delete()

    async def check_playtest(self, map_code: str):
        return bool(
            await self.bot.database.get_row(
                "SELECT * FROM playtest WHERE map_code = $1", map_code
            )
        )

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def legacy_completions(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
    ) -> None:
        await itx.response.defer(ephemeral=True)
        if map_code not in itx.client.cache.maps.keys:
            raise utils.InvalidMapCodeError

        query = f"""
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
                WHERE lr.map_code = $1
                GROUP BY u.nickname, record, screenshot, video, lr.map_code, lr.channel_id, lr.message_id, m.map_name, medal
                ORDER BY record;
                """

        records: list[database.DotRecord | None] = [
            x async for x in itx.client.database.get(query, map_code)
        ]
        if not records:
            raise utils.NoRecordsFoundError

        embeds = utils.all_levels_records_embed(
            records,
            f"Legacy Leaderboard - {map_code}",
            legacy=True,
        )

        view = views.Paginator(embeds, itx.user)
        await view.start(itx)

    @app_commands.command(name="completions")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def view_records(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
        filters: typing.Literal["Fully Verified", "Verified", "Completions", "All"]
        | None = "All",
    ) -> None:
        """
        View leaderboard/completions for any map in the database.
        You are able to filter by Fully Verified, Verified, Completions or All.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            filters: Type of submissions to show
        """
        await itx.response.defer(ephemeral=True)
        if map_code not in itx.client.cache.maps.keys:
            raise utils.InvalidMapCodeError

        query = f"""
        SELECT * FROM (
        SELECT u.nickname, 
               record, 
               screenshot,
               video, 
               verified,
               r.map_code,
               r.channel_id,
               r.message_id,
               m.map_name,
               avg(difficulty) as difficulty
        FROM records r
            LEFT JOIN users u on r.user_id = u.user_id
            LEFT JOIN maps m on m.map_code = r.map_code
            LEFT JOIN map_ratings mr on m.map_code = mr.map_code
            GROUP BY u.nickname, record, screenshot, video, verified, r.map_code, r.channel_id, r.message_id, m.map_name
        ) as ranks
        LEFT JOIN map_medals mm ON ranks.map_code = mm.map_code
        WHERE ranks.map_code = $1 
        AND ($2::text != 'Fully Verified' OR (verified = TRUE AND record < 99999999))
        AND ($2::text != 'Verified' OR record < 99999999)
        AND ($2::text != 'Completions' OR record > 99999999)
        ORDER BY record;
        """

        records: list[database.DotRecord | None] = [
            x async for x in itx.client.database.get(query, map_code, filters)
        ]
        if not records:
            raise utils.NoRecordsFoundError

        embeds = utils.all_levels_records_embed(
            records, f"{filters} Leaderboard - {map_code}"
        )

        view = views.Paginator(embeds, itx.user)
        await view.start(itx)

    @app_commands.command(name="personal-records")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def personal_records_slash(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[
            int | discord.Member | utils.FakeUser, utils.AllUserTransformer
        ]
        | None = None,
        filters: typing.Literal["All", "World Records", "Completions", "Records"]
        | None = "All",
    ):
        """
        Show all records a specific user has (fully AND partially verified)

        Args:
            itx: Interaction
            user: User
            filters: Filter submissions by All, World Records, Completions, or Records
        """
        await self._personal_records(itx, user, filters)

    async def pr_context_callback(
        self, itx: discord.Interaction[core.Genji], user: discord.Member
    ):
        await self._personal_records(itx, user, "Records")

    async def wr_context_callback(
        self, itx: discord.Interaction[core.Genji], user: discord.Member
    ):
        await self._personal_records(itx, user, "World Records")

    async def completion_context_callback(
        self, itx: discord.Interaction[core.Genji], user: discord.Member
    ):
        await self._personal_records(itx, user, "Completions")

    @staticmethod
    async def _personal_records(
        itx: discord.Interaction[core.Genji],
        user: discord.Member | str,
        filters: PR_TYPES,
    ):
        await itx.response.defer(ephemeral=True)
        if not user:
            user = itx.user

        if isinstance(user, discord.Member) or isinstance(user, utils.FakeUser):
            user = user.id
        else:
            user = int(user)

        query = f"""
        WITH map AS (SELECT m.map_code,
                    m.map_name,
                    string_agg(distinct (nickname), ', ') as creators,
                    avg(difficulty) as difficulty
             FROM maps m
                      LEFT JOIN map_creators mc on m.map_code = mc.map_code
                      LEFT JOIN users u on mc.user_id = u.user_id
                      LEFT JOIN map_ratings mr on m.map_code = mr.map_code
             GROUP BY m.map_code, m.map_name),
        ranks AS (SELECT u.nickname,
                        r.user_id,
                        record,
                        screenshot,
                        video,
                        verified,
                        r.map_code,
                        r.channel_id,
                        r.message_id,
                        map.map_name,
                        map.creators,
                        difficulty,
                        RANK() OVER (
                            PARTITION BY r.map_code
                            ORDER BY record
                        ) rank_num
                        FROM records r
                        LEFT JOIN users u
                              on r.user_id = u.user_id
                        LEFT JOIN map on map.map_code = r.map_code)
        SELECT 
            nickname,
            user_id,
            record,
            screenshot,
            video,
            verified,
            ranks.map_code,
            channel_id,
            message_id,
            map_name,
            creators,
            rank_num,
            gold,
            silver,
            bronze,
            difficulty
        FROM ranks
                 LEFT JOIN map_medals mm ON ranks.map_code = mm.map_code
        WHERE user_id = $1 
        AND ($2::text != 'World Records' OR rank_num = 1 AND record < 99999999 AND verified = TRUE)
        AND ($2::text != 'Records' OR record < 99999999)
        AND ($2::text != 'Completions' OR record > 99999999)
        ORDER BY difficulty, ranks.map_code;     
        """
        records: list[database.DotRecord | None] = [
            x async for x in itx.client.database.get(query, user, filters)
        ]

        if not records:
            raise utils.NoRecordsFoundError
        embeds = utils.pr_records_embed(
            records,
            f"Personal {filters} | {itx.client.cache.users[user].nickname}",
        )
        view = views.Paginator(embeds, itx.user)
        await view.start(itx)


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(Records(bot))
