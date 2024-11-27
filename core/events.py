from __future__ import annotations

import contextlib
import json
import logging
import re
import typing

import asyncpg
import discord
from discord.ext import commands

import views
from cogs.info_pages.views import CompletionInfoView, MapInfoView
from cogs.tickets.views import TicketStart
from utils import cache, constants, embeds, errors, maps, ranks, records, utils
from utils.records import icon_generator

if typing.TYPE_CHECKING:
    import database

    from .genji import Genji

log = logging.getLogger(__name__)

ASCII_LOGO = r""""""


class BotEvents(commands.Cog):
    def __init__(self, bot: Genji) -> None:
        self.bot = bot
        bot.tree.on_error = errors.on_app_command_error

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != 975820285343301674:
            return
        if "<@1309606801750360186>" not in message.content:
            return
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2)"
        nickname = self.bot.database.fetch_nickname(message.author.id)
        data = {
            "user": {
                "user_id": message.author.id,
                "nickname": nickname,
            },
            "message": {
                "content": message.content,
            },
        }
        json_data = json.dumps(data)
        await self.bot.database.execute(query, "announcement", json_data)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Call upon ready.

        The on_ready function is called when the bot
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
                        creator=await records.transform_user(self.bot, x.creator_ids[0]),
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
            queue = [x async for x in self.bot.database.get("SELECT * FROM polls_info;")]
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
    async def on_member_join(self, member: discord.Member) -> None:
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
            await member.add_roles(map_maker, reason="User rejoined. Re-granting map maker.")
        if (ninja := member.guild.get_role(constants.Roles.NINJA)) is not None and ninja not in member.roles:
            await member.add_roles(ninja, reason="User joined. Granting Ninja.")

        await utils.auto_skill_role(self.bot, member.guild, member)

    @commands.Cog.listener()
    async def on_newsfeed_role(self, client: Genji, user: discord.Member, roles: list[discord.Role]) -> None:
        nickname = client.cache.users[user.id].nickname
        embed = embeds.GenjiEmbed(
            title=f"{nickname} got promoted!",
            description="\n".join([f"{x.mention}" for x in roles]),
            color=discord.Color.green(),
        )
        await client.get_guild(constants.GUILD_ID).get_channel(constants.NEWSFEED).send(embed=embed)
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
    async def on_newsfeed_map_edit(
        self,
        itx: discord.Interaction[Genji],
        map_code: str,
        values: dict[str, str],
        thread_id: int | None = None,
        message_id: int | None = None,
    ) -> None:
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
            original = await itx.guild.get_channel(constants.PLAYTEST).fetch_message(message_id)
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
    """Add cog to bot."""
    await bot.add_cog(BotEvents(bot))
