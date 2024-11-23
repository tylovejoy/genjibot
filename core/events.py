from __future__ import annotations

import contextlib
import json
import logging
import re
import typing

import asyncpg
import discord
from discord.ext import commands

import core
import database
import views
from cogs.info_pages.views import CompletionInfoView, MapInfoView
from cogs.tickets.views import TicketStart
from utils import cache, constants, embeds, errors, maps, ranks, records, utils
from utils.records import icon_generator

if typing.TYPE_CHECKING:
    from .genji import Genji

log = logging.getLogger(__name__)

ASCII_LOGO = r""""""


class BotEvents(commands.Cog):
    def __init__(self, bot: Genji):
        self.bot = bot
        bot.tree.on_error = errors.on_app_command_error

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """The on_ready function is called when the bot
        is ready to receive and process commands.
        It prints a string containing the name of the bot,
        its owner, and which version of discord.py it's using.
        """
        app_info = await self.bot.application_info()
        log.info(
            f"{ASCII_LOGO}"
            f"\nLogged in as: {self.bot.user.name}\n"
            f"Using discord.py version: {discord.__version__}\n"
            f"Owner: {app_info.owner}\n"
        )
        if not self.bot.persistent_views_added:
            queue = [
                x.hidden_id
                async for x in self.bot.database.get(
                    "SELECT hidden_id FROM records WHERE verified = FALSE;",
                )
            ]
            for x in queue:
                self.bot.add_view(views.VerificationView(), message_id=x)

            view = views.AnnouncementRoles()
            self.bot.add_view(view, message_id=1073294355613360129)
            await (
                self.bot.get_channel(constants.ROLE_REACT)
                .get_partial_message(1073294355613360129)
                .edit(
                    content="**Announcement Pings**",
                    view=view,
                )
            )

            view = views.RegionRoles()
            self.bot.add_view(view, message_id=1073294377050460253)
            await (
                self.bot.get_channel(constants.ROLE_REACT)
                .get_partial_message(1073294377050460253)
                .edit(
                    content="**Regions**",
                    view=view,
                )
            )

            view = views.ConsoleRoles()
            self.bot.add_view(view, message_id=1073294381311873114)
            await (
                self.bot.get_channel(constants.ROLE_REACT)
                .get_partial_message(1073294381311873114)
                .edit(
                    content="**Platform**",
                    view=view,
                )
            )

            queue = await maps.get_map_info(self.bot)
            for x in queue:
                if x is None:
                    continue
                try:
                    data = maps.MapSubmission(
                        creator=await records.transform_user(
                            self.bot, x.creator_ids[0]
                        ),
                        map_code=x.map_code,
                        map_name=x.map_name,
                        checkpoint_count=x.checkpoints,
                        description=x.desc,
                        guides=x.guide,
                        medals=(x.gold, x.silver, x.bronze),
                        map_types=x.map_type,
                        mechanics=x.mechanics,
                        restrictions=x.restrictions,
                        difficulty=ranks.convert_num_to_difficulty(x.value),
                    )

                    with contextlib.suppress(AttributeError):
                        view = views.PlaytestVoting(
                            data,
                            self.bot,
                        )
                        self.bot.add_view(
                            view,
                            message_id=x.message_id,
                        )
                        self.bot.playtest_views[x.message_id] = view
                except Exception:
                    ...
            queue = [
                x async for x in self.bot.database.get("SELECT * FROM polls_info;")
            ]
            for x in queue:
                self.bot.add_view(
                    views.PollView(
                        x.options,
                        x.title,
                    ),
                    message_id=x.message_id,
                )

            view = CompletionInfoView()
            self.bot.add_view(view, message_id=1118917201894850592)

            view = MapInfoView()
            self.bot.add_view(view, message_id=1118917508934664212)

            view = TicketStart()
            self.bot.add_view(view, message_id=1120076353597886565)

            log.debug("Added persistent views.")
            self.bot.persistent_views_added = True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Add user to DB
        with contextlib.suppress(asyncpg.UniqueViolationError):
            await self.bot.database.set(
                "INSERT INTO users VALUES ($1, $2, true);",
                member.id,
                member.name[:25],
            )
        if not self.bot.cache.users[member.id]:
            self.bot.cache.users.add_one(
                cache.UserData(
                    user_id=member.id,
                    nickname=member.name[:25],
                    flags=cache.SettingFlags.DEFAULT,
                    is_creator=False,
                )
            )

        log.debug(f"Adding user to DB/cache: {member.name}: {member.id}")
        res = [
            x
            async for x in self.bot.database.get(
                """
            SELECT * FROM maps 
            LEFT JOIN map_creators mc on maps.map_code = mc.map_code
            WHERE user_id = $1;
            """,
                member.id,
            )
        ]
        if res and (
            (map_maker := member.guild.get_role(constants.Roles.MAP_MAKER)) is not None
            and map_maker not in member.roles
        ):
            await member.add_roles(
                map_maker, reason="User rejoined. Re-granting map maker."
            )
        if (
            ninja := member.guild.get_role(constants.Roles.NINJA)
        ) is not None and ninja not in member.roles:
            await member.add_roles(ninja, reason="User joined. Granting Ninja.")

        await utils.auto_role(self.bot, member)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # members = [(member.id, member.name[:25]) for member in guild.members]
        # await self.bot.database.set_many(
        #     "INSERT INTO users (user_id, nickname, alertable) VALUES ($1, $2, true)",
        #     [(_id, nick) for _id, nick in members],
        # )
        ...

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        # if before.parent_id not in self.bot.keep_alives:
        #     return
        #
        # if after.archived and not after.locked:
        #     await after.edit(archived=False)
        #     log.debug(f"Auto-unarchived thread: {after.id}")
        ...

    # async def newsfeed_worker(
    #     self, data: dict, guild: discord.Guild, db: database.Database
    # ):
    #
    #     query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
    #     await db.execute(query, "record", data)
    #
    #     channel = guild.get_channel(utils.NEWSFEED)
    #     await channel.send(embed=embed)

    async def newsfeed_record(
        self,
        guild: discord.Guild,
        record: database.DotRecord,
        medals: tuple[float, float, float],
    ): ...

    @commands.Cog.listener()
    async def on_newsfeed_record(
        self,
        itx: discord.Interaction[core.Genji],
        record: asyncpg.Record,
        medals: tuple[float, float, float],
    ):
        if not record["video"]:
            return
        icon = icon_generator(record, medals)
        embed = embeds.GenjiEmbed(
            url=record["screenshot"],
            description=(
                f"**{record['map_name']} by {record['creators']} ({record['map_code']})**\n"
                f"┣ `Record` {record['record']} {icon}\n"
                f"┗ `Video` [Link]({record['video']})"
                if record["video"]
                else ""
            ),
            color=discord.Color.yellow(),
        )

        if record["rank_num"] == 1:
            embed.title = f"{record['nickname']} set a new World Record!"
        elif icon in [constants.PARTIAL_VERIFIED, constants.FULLY_VERIFIED]:
            return
        else:
            embed.title = f"{record['nickname']} got a medal!"
        await itx.guild.get_channel(constants.NEWSFEED).send(embed=embed)

        data = {
            "map": {
                "map_code": record["map_code"],
                "map_name": record["map_name"],
                "creators": record["creators"],
            },
            "record": {
                "record": record["record"],
                "video": record["video"],
            },
            "user": {
                "user_id": record["user_id"],
                "nickname": record["nickname"],
            },
        }
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
        json_data = json.dumps(data)
        await itx.client.database.execute(query, "record", json_data)

    @commands.Cog.listener()
    async def on_newsfeed_role(
        self, client: core.Genji, user: discord.Member, roles: list[discord.Role]
    ):
        nickname = client.cache.users[user.id].nickname
        embed = embeds.GenjiEmbed(
            title=f"{nickname} got promoted!",
            description="\n".join([f"{x.mention}" for x in roles]),
            color=discord.Color.green(),
        )
        await client.get_guild(constants.GUILD_ID).get_channel(constants.NEWSFEED).send(
            embed=embed
        )
        data = {
            "user": {
                "user_id": user.id,
                "nickname": nickname,
                "roles": [role.name for role in roles],
            },
        }
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
        json_data = json.dumps(data)
        await client.database.execute(query, "role", json_data)

    @commands.Cog.listener()
    async def on_newsfeed_guide(
        self,
        itx: discord.Interaction[core.Genji],
        user: discord.Member,
        url: str,
        map_code: str,
    ):
        nickname = itx.client.cache.users[user.id].nickname
        embed = embeds.GenjiEmbed(
            title=f"{nickname} has posted a guide for {map_code}",
            url=url,
            color=discord.Color.orange(),
        )
        await itx.guild.get_channel(constants.NEWSFEED).send(embed=embed)
        await itx.guild.get_channel(constants.NEWSFEED).send(url)
        data = {
            "user": {
                "user_id": user.id,
                "nickname": nickname,
            },
            "map": {
                "map_code": map_code,
                "url": url,
            },
        }
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
        json_data = json.dumps(data)
        await itx.client.database.execute(query, "guide", json_data)

    @commands.Cog.listener()
    async def on_newsfeed_archive(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: str,
        value: str,
        map_data: dict = None,
    ):
        if value == "archive":
            description = (
                "This map will not appear in the map search command.\n"
                "You cannot submit records for archived maps."
            )
        else:
            description = (
                "This map will now appear in the map search command "
                "and be eligible for record submissions."
            )
        embed = embeds.GenjiEmbed(
            title=f"{map_code} has been {value}d.",
            description=description,
            color=discord.Color.red(),
        )
        if value:
            guide_txt = ""
            medals_txt = ""
            if map_data.get("guide") and None not in map_data.get("guide"):
                guides = [
                    f"[{j}]({guide})" for j, guide in enumerate(map_data.guide, 1)
                ]
                guide_txt = f"┣ `Guide(s)` {', '.join(guides)}\n"
            if map_data.gold:
                medals_txt = (
                    f"┣ `Medals` "
                    f"{constants.FULLY_VERIFIED_GOLD} {map_data.gold} | "
                    f"{constants.FULLY_VERIFIED_SILVER} {map_data.silver} | "
                    f"{constants.FULLY_VERIFIED_BRONZE} {map_data.bronze}\n"
                )

            embed.add_description_field(
                name=f"{map_data.map_code}",
                value=(
                    f"┣ `Rating` {constants.create_stars(map_data.quality)}\n"
                    f"┣ `Creator` {discord.utils.escape_markdown(map_data.creators)}\n"
                    f"┣ `Map` {map_data.map_name}\n"
                    f"┣ `Difficulty` {ranks.convert_num_to_difficulty(map_data.difficulty)}\n"
                    f"┣ `Mechanics` {map_data.mechanics}\n"
                    f"┣ `Restrictions` {map_data.restrictions}\n"
                    f"{guide_txt}"
                    f"┣ `Type` {map_data.map_type}\n"
                    f"┣ `Checkpoints` {map_data.checkpoints}\n"
                    f"{medals_txt}"
                    f"┗ `Desc` {map_data.desc}"
                ),
            )
        await itx.guild.get_channel(constants.NEWSFEED).send(embed=embed)
        data = {
            "map": map_data,
        }
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
        json_data = json.dumps(data)
        await itx.client.database.execute(query, value, json_data)

    @commands.Cog.listener()
    async def on_newsfeed_map_edit(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: str,
        values: dict[str, str],
        thread_id: int | None = None,
        message_id: int | None = None,
    ):
        description = ">>> "
        for k, v in values.items():
            description += f"`{k}` {v}\n"

        embed = embeds.GenjiEmbed(
            title=f"{map_code} has been changed:",
            description=description,
            color=discord.Color.red(),
        )
        if thread_id:
            thread = itx.guild.get_thread(thread_id)
            row = await self.bot.database.get_row(
                """
                  SELECT
                    map_name,
                    m.map_code,
                    checkpoints,
                    value AS difficulty
                    FROM
                      maps m
                        LEFT JOIN playtest p ON m.map_code = p.map_code AND p.is_author = TRUE
                    WHERE m.map_code = $1
                """,
                values.get("Code") or map_code,
            )

            await thread.edit(
                name=(
                    f"{values.get('Code') or map_code} | {ranks.convert_num_to_difficulty(row.difficulty)} "
                    f"| {row.map_name} | {row.checkpoints} CPs"
                )
            )
            await thread.send(embed=embed)
            original = await itx.guild.get_channel(constants.PLAYTEST).fetch_message(
                message_id
            )
            embed = None
            for k, v in values.items():
                embed = self.edit_embed(original.embeds[0], k, v)
            await original.edit(embed=embed)
        else:
            await itx.guild.get_channel(constants.NEWSFEED).send(embed=embed)

    @staticmethod
    def edit_embed(embed: discord.Embed, field: str, value: str) -> discord.Embed:
        # TODO: missing fields dont get edited
        pattern = re.compile(r"(┣?┗?) `" + field + r"` (.+)(\n?┣?┗?)")
        search = re.search(pattern, embed.description)

        if search:
            start_char = search.group(1)
            end_char = search.group(3)

            embed.description = re.sub(
                pattern,
                f"{start_char} `{field}` {value}{end_char}",
                embed.description,
            )
        else:
            last_field_pattern = re.compile(r"(┣?.+\n)┗")
            last_field = re.search(last_field_pattern, embed.description)
            new_field = f"{last_field.group(1)}┣ `{field}` {value}\n┗"
            embed.description = re.sub(
                last_field_pattern,
                new_field,
                embed.description,
            )

        return embed


async def setup(bot: Genji) -> None:
    await bot.add_cog(BotEvents(bot))
