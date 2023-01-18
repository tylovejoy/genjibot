from __future__ import annotations

import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

import core
import database
import utils
import views

if typing.TYPE_CHECKING:
    from .genji import Genji

ASCII_LOGO = r""""""


class BotEvents(commands.Cog):
    def __init__(self, bot: Genji):
        self.bot = bot
        bot.tree.on_error = utils.on_app_command_error

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        ...

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        The on_ready function is called when the bot
        is ready to receive and process commands.
        It prints a string containing the name of the bot,
        its owner, and which version of discord.py it's using.
        Args:
            self: Bot instance
        """
        app_info = await self.bot.application_info()
        self.bot.logger.info(
            f"{ASCII_LOGO}"
            f"\nLogged in as: {self.bot.user.name}\n"
            f"Using discord.py version: {discord.__version__}\n"
            f"Owner: {app_info.owner}\n"
        )
        if not self.bot.persistent_views_added:
            queue = [
                x.hidden_id
                async for x in self.bot.database.get(
                    "SELECT hidden_id FROM records_queue;",
                )
            ]
            for x in queue:
                self.bot.add_view(views.VerificationView(), message_id=x)

            # TODO: Hardcoded LIVE
            view = views.RegionRoles()
            self.bot.add_view(view, message_id=1054834412409339904)
            await self.bot.get_channel(1054834201444220948).get_partial_message(
                1054834412409339904
            ).edit(
                content="Press the button to add or remove your preferred region.",
                view=view,
            )

            view = views.ConsoleRoles()
            self.bot.add_view(view, message_id=1060610579007553536)
            await self.bot.get_channel(1054834201444220948).get_partial_message(
                1060610579007553536
            ).edit(
                content="Choose how you play.",
                view=view,
            )

            queue = [
                x
                async for x in self.bot.database.get(
                    "SELECT map_code, message_id, value, user_id "
                    "FROM playtest WHERE is_author = TRUE;"
                )
            ]
            for x in queue:
                self.bot.add_view(
                    views.PlaytestVoting(
                        x.map_code,
                        utils.convert_num_to_difficulty(x.value),
                        x.user_id,
                        self.bot,
                        x.message_id,
                    ),
                    message_id=x.message_id,
                )

            self.bot.logger.debug(f"Added persistent views.")
            self.bot.persistent_views_added = True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        ...

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Add user to DB
        await self.bot.database.set(
            "INSERT INTO users VALUES ($1, $2, true);",
            member.id,
            member.name[:25],
        )

        # Add user to cache
        self.bot.all_users[member.id] = utils.UserCacheData(
            nickname=member.nick, alertable=True
        )
        self.bot.users_choices.append(
            app_commands.Choice(name=member.nick, value=str(member.id))
        )
        self.bot.logger.debug(f"Adding user to DB/cache: {member.name}: {member.id}")
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
            map_maker := member.guild.get_role(utils.Roles.MAP_MAKER)
            not in member.roles
        ):
            await member.add_roles(
                map_maker, reason="User rejoined. Re-granting map maker."
            )
        if ninja := member.guild.get_role(utils.Roles.NINJA) not in member.roles:
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
        #     self.bot.logger.debug(f"Auto-unarchived thread: {after.id}")
        ...

    @commands.Cog.listener()
    async def on_newsfeed_record(
        self,
        itx: core.Interaction[core.Genji],
        record: database.DotRecord,
        medals: tuple[float, float, float],
    ):
        if not record.video:
            return
        icon = utils.icon_generator(record, medals)
        embed = utils.GenjiEmbed(
            url=record.screenshot,
            description=(
                f"**{record.map_name} by {record.creators} ({record.map_code})**\n"
                f"┣ `Record` {record.record} {icon}\n"
                f"┗ `Video` [Link]({record.video})"
                if record.video
                else ""
            ),
            color=discord.Color.yellow(),
        )

        if record.rank_num == 1:
            embed.title = f"{record.nickname} set a new World Record!"
        else:
            embed.title = f"{record.nickname} got a medal!"
        await itx.guild.get_channel(utils.NEWSFEED).send(embed=embed)

    @commands.Cog.listener()
    async def on_newsfeed_role(
        self, client: core.Genji, user: discord.Member, roles: list[discord.Role]
    ):
        nickname = client.all_users[user.id]["nickname"]
        embed = utils.GenjiEmbed(
            title=f"{nickname} got promoted!",
            description="\n".join([f"{x.mention}" for x in roles]),
            color=discord.Color.green(),
        )
        await client.get_guild(utils.GUILD_ID).get_channel(utils.NEWSFEED).send(
            embed=embed
        )

    @commands.Cog.listener()
    async def on_newsfeed_guide(
        self,
        itx: core.Interaction[core.Genji],
        user: discord.Member,
        url: str,
        map_code: str,
    ):
        nickname = itx.client.all_users[user.id]["nickname"]
        embed = utils.GenjiEmbed(
            title=f"{nickname} has posted a guide for {map_code}",
            url=url,
            color=discord.Color.orange(),
        )
        await itx.guild.get_channel(utils.NEWSFEED).send(embed=embed)
        await itx.guild.get_channel(utils.NEWSFEED).send(url)

    @commands.Cog.listener()
    async def on_newsfeed_new_map(
        self,
        itx: core.Interaction[core.Genji],
        user: discord.Member,
        url: str,
        map_code: str,
    ):
        nickname = itx.client.all_users[user.id]["nickname"]
        embed = utils.GenjiEmbed(
            title=f"{nickname} has submitted a new map!",
            description=f"[Check out {map_code} here!]({url})",
            url=url,
            color=discord.Color.blue(),
        )
        await itx.guild.get_channel(utils.NEWSFEED).send(embed=embed)

    @commands.Cog.listener()
    async def on_newsfeed_medals(
        self,
        itx: core.Interaction[core.Genji],
        map_code: str,
        gold: float,
        silver: float,
        bronze: float,
        thread_id: int | None = None,
        message_id: int | None = None,
    ):
        embed = utils.GenjiEmbed(
            title=f"Medals have been added/changed for code {map_code}",
            description=f"`Gold` {gold}\n"
            f"`Silver` {silver}\n"
            f"`Bronze` {bronze}\n",
            color=discord.Color.red(),
        )

        if thread_id:
            await itx.guild.get_thread(thread_id).send(embed=embed)
            original = await itx.guild.get_channel(utils.PLAYTEST).fetch_message(
                message_id
            )
            embed = self.edit_medals(original.embeds[0], gold, silver, bronze)
            await original.edit(embed=embed)
        else:
            await itx.guild.get_channel(utils.NEWSFEED).send(embed=embed)

    @commands.Cog.listener()
    async def on_newsfeed_archive(
        self,
        itx: core.Interaction[core.Genji],
        map_code: str,
        value: str,
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
        embed = utils.GenjiEmbed(
            title=f"{map_code} has been {value}d.",
            description=description,
            color=discord.Color.red(),
        )
        await itx.guild.get_channel(utils.NEWSFEED).send(embed=embed)

    commands.Cog.listener()

    @commands.Cog.listener()
    async def on_newsfeed_map_edit(
        self,
        itx: core.Interaction[core.Genji],
        map_code: str,
        values: dict[str, str],
        thread_id: int | None = None,
        message_id: int | None = None,
    ):
        description = ">>> "
        for k, v in values.items():
            description += f"`{k}` {v}\n"

        embed = utils.GenjiEmbed(
            title=f"{map_code} has been changed:",
            description=description,
            color=discord.Color.red(),
        )
        if thread_id:
            await itx.guild.get_thread(thread_id).send(embed=embed)
            original = await itx.guild.get_channel(utils.PLAYTEST).fetch_message(
                message_id
            )
            embed = None
            for k, v in values.items():
                if k == "Desc":
                    embed = self.edit_description(original.embeds[0], v)
                else:
                    embed = self.edit_embed(original.embeds[0], k, v)
            await original.edit(embed=embed)
        else:
            await itx.guild.get_channel(utils.NEWSFEED).send(embed=embed)

    @staticmethod
    def edit_embed(embed: discord.Embed, field: str, value: str) -> discord.Embed:
        embed.description = re.sub(
            f"┣ `{field}" + r"` (.+)\n┣",
            f"┣ `{field}` {value}\n┣",
            embed.description,
        )
        return embed

    @staticmethod
    def edit_description(embed: discord.Embed, value: str) -> discord.Embed:
        embed.description = re.sub(
            f"┗ `Desc` (.+)",
            f"┗ `Desc` {value}",
            embed.description,
        )
        return embed

    @staticmethod
    def edit_medals(embed: discord.Embed, gold, silver, bronze) -> discord.Embed:
        medals_txt = (
            f"┣ `Medals` "
            f"{utils.FULLY_VERIFIED_GOLD} {gold} | "
            f"{utils.FULLY_VERIFIED_SILVER} {silver} | "
            f"{utils.FULLY_VERIFIED_BRONZE} {bronze}\n┗"
        )
        if bool(re.search("`Medals`", embed.description)):
            embed.description = re.sub(
                r"┣ `Medals` (.+)\n┗",
                medals_txt,
                embed.description,
            )
        else:
            embed.description = re.sub(
                r"┗",
                medals_txt,
                embed.description,
            )
        return embed


async def setup(bot: Genji) -> None:
    await bot.add_cog(BotEvents(bot))
