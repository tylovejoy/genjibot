from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import utils
import views

if typing.TYPE_CHECKING:
    import core


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

    @app_commands.command()
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def summary(
        self,
        itx: core.Interaction[core.Genji],
        user: str | None = None,
    ):
        """Display a summary of your records and associated difficulties/medals

        Args:
            itx: Interaction
            user: User
        """
        await itx.response.defer(ephemeral=True)
        if not user:
            user = itx.user

        if isinstance(user, discord.Member):
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

    @app_commands.command(name="submit-record")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def submit_record(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
        record: app_commands.Transform[float, utils.RecordTransformer],
        screenshot: discord.Attachment,
        video: app_commands.Transform[str, utils.URLTransformer] | None,
    ) -> None:
        """
        Submit a record to the database. Video proof is required for full verification!

        Args:
            itx: Interaction
            map_code: Overwatch share code
            record: Record in HH:MM:SS.ss format
            screenshot: Screenshot of completion
            video: Video of play through. REQUIRED FOR FULL VERIFICATION!
        """
        await itx.response.defer(ephemeral=False)
        if map_code not in itx.client.map_cache.keys():
            raise utils.InvalidMapCodeError

        if itx.client.map_cache[map_code]["archived"] is False:
            raise utils.ArchivedMap

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
            if search.record < record and not (not search.video and video):
                raise utils.RecordNotFasterError

        user = itx.client.all_users[itx.user.id]
        view = views.ConfirmCompletion(
            await utils.Roles.find_highest_rank(itx.user) + 1,
            itx,
            f"{utils.TIME} Waiting for verification...\n",
        )

        new_screenshot = await screenshot.to_file(filename="image.png")

        embed = utils.record_embed(
            {
                "map_code": map_code,
                "record": record,
                "video": video,
                "user_name": user["nickname"],
                "user_url": itx.user.display_avatar.url,
            }
        )
        channel_msg = await itx.edit_original_response(
            content=f"{itx.user.mention}, is this correct?",
            embed=embed,
            view=view,
            attachments=[new_screenshot],
        )
        await view.wait()
        if not view.value:
            return
        new_screenshot2 = await screenshot.to_file(filename="image.png")
        verification_msg = await itx.client.get_channel(utils.VERIFICATION_QUEUE).send(
            embed=embed, file=new_screenshot2
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
            record,
            channel_msg.jump_url,
            video,
            channel_msg.id,
            channel_msg.channel.id,
            verification_msg.id,
            None if not getattr(view, "quality", None) else int(view.quality.values[0]),
        )

    @app_commands.command(name="leaderboard")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def view_records(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
        verified: bool | None = True,
    ) -> None:
        """
        View leaderboard of any map in the database.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            verified: Only show fully verified video submissions.
        """
        await itx.response.defer(ephemeral=True)
        if map_code not in itx.client.map_cache.keys():
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
               m.map_name
        FROM records r
            LEFT JOIN users u on r.user_id = u.user_id
            LEFT JOIN maps m on m.map_code = r.map_code
        ) as ranks
        LEFT JOIN map_medals mm ON ranks.map_code = mm.map_code
        WHERE ranks.map_code=$1 
        AND ($2 IS FALSE OR verified=$2)
        ORDER BY record;
        """

        records = [x async for x in itx.client.database.get(query, map_code, verified)]
        if not records:
            raise utils.NoRecordsFoundError

        embeds = utils.all_levels_records_embed(records, f"Leaderboard - {map_code}")

        view = views.Paginator(embeds, itx.user)
        await view.start(itx)

    @app_commands.command(name="personal-records")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(user=cogs.users_autocomplete)
    async def personal_records_slash(
        self,
        itx: core.Interaction[core.Genji],
        user: str | None = None,
        wr_only: bool | None = None,
    ):
        """
        Show all records a specific user has (fully AND partially verified)

        Args:
            itx: Interaction
            user: User
            wr_only: Only show world records
        """
        await self._personal_records(itx, user, wr_only)

    async def pr_context_callback(
        self, itx: core.Interaction[core.Genji], user: discord.Member
    ):
        await self._personal_records(itx, user, False)

    async def wr_context_callback(
        self, itx: core.Interaction[core.Genji], user: discord.Member
    ):
        await self._personal_records(itx, user, True)

    @staticmethod
    async def _personal_records(
        itx: core.Interaction[core.Genji],
        user: discord.Member | str,
        wr_only: bool,
    ):
        await itx.response.defer(ephemeral=True)
        if not user:
            user = itx.user

        if isinstance(user, discord.Member):
            user = user.id
        else:
            user = int(user)

        query = f"""
        WITH map AS (SELECT m.map_code,
                    m.map_name,
                    string_agg(distinct (nickname), ', ') as creators
             FROM maps m
                      LEFT JOIN map_creators mc on m.map_code = mc.map_code
                      LEFT JOIN users u on mc.user_id = u.user_id
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
                        RANK() OVER (
                            PARTITION BY r.map_code
                            ORDER BY record
                        ) rank_num
                        FROM records r
                        LEFT JOIN users u
                              on r.user_id = u.user_id
                        LEFT JOIN map on map.map_code = r.map_code)
        SELECT *
        FROM ranks
                 LEFT JOIN map_medals mm ON ranks.map_code = mm.map_code
        WHERE user_id = $1 
        AND ($2 IS FALSE OR rank_num = 1)
        ORDER BY ranks.map_code;     
        """
        # print(query, user, wr_only, sep="\n\n\n\n")
        records = [x async for x in itx.client.database.get(query, user, wr_only)]
        if not records:
            raise utils.NoRecordsFoundError
        embeds = utils.pr_records_embed(
            records,
            f"Personal {'World ' if wr_only else ''}Records | {itx.client.all_users[user]['nickname']}",
        )
        view = views.Paginator(embeds, itx.user)
        await view.start(itx)


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(Records(bot))
