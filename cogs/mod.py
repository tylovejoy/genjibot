from __future__ import annotations

import copy
import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import utils
import utils.autocomplete
import utils.maps
import views
from cogs.command_groups import map_commands, mod_commands
from database import DotRecord
from utils import NEWSFEED

if typing.TYPE_CHECKING:
    import core


class ModCommands(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context[core.Genji]) -> bool:
        return True

    @mod_commands.command(name="remove-record")
    @app_commands.autocomplete(
        map_code=utils.autocomplete.map_codes_autocomplete,
    )
    async def remove_record(
        self,
        itx: discord.Interaction[core.Genji],
        member: discord.Member,
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
    ):
        """
        Remove a record from the database/user

        Args:
            itx: Interaction
            member: User
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        record = [
            x
            async for x in self.bot.database.get(
                "SELECT * FROM records r "
                "LEFT JOIN users u on r.user_id = u.user_id "
                "WHERE r.user_id=$1 AND map_code=$2",
                member.id,
                map_code,
            )
        ]
        if not record:
            raise utils.NoRecordsFoundError

        record = record[0]
        embed = utils.GenjiEmbed(
            title="Delete Record",
            description=(
                f"`Name` {discord.utils.escape_markdown(record.nickname)}\n"
                f"`Code` {record.map_code}\n"
                f"`Record` {record.record}\n"
                # f"`Level` {record.level_name}\n"
            ),
        )
        view = views.Confirm(itx)
        await itx.edit_original_response(
            content="Delete this record?", embed=embed, view=view
        )
        await view.wait()

        if not view.value:
            return

        await self.bot.database.set(
            "DELETE FROM records WHERE user_id=$1 AND map_code=$2",
            member.id,
            map_code,
        )

        await member.send(f"Your record for {map_code} has been deleted by staff.")
        await utils.auto_role(itx.client, member)

    @mod_commands.command(name="change-name")
    @app_commands.autocomplete(member=utils.autocomplete.users_autocomplete)
    async def change_name(
        self,
        itx: discord.Interaction[core.Genji],
        member: app_commands.Transform[int, utils.UserTransformer],
        nickname: app_commands.Range[str, 1, 25],
    ):
        """
        Change a user display name.

        Args:
            itx: Interaction
            member: User
            nickname: New nickname
        """
        old = self.bot.cache.users[member].nickname
        self.bot.cache.users[member].update_nickname(nickname)
        await self.bot.database.set(
            "UPDATE users SET nickname=$1 WHERE user_id=$2", nickname, member
        )
        await itx.response.send_message(
            f"Changing {old} ({member}) nickname to {nickname}",
            ephemeral=True,
        )

    @mod_commands.command(name="create-fake-member")
    async def create_fake_member(
        self,
        itx: discord.Interaction[core.Genji],
        fake_user: str,
    ):
        """
        Create a fake user. MAKE SURE THIS USER DOESN'T ALREADY EXIST!

        Args:
            itx: Discord itx
            fake_user: The fake user
        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(itx, ephemeral=True)
        await itx.edit_original_response(
            content=f"Create fake user {fake_user}?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        value = (
            await itx.client.database.get_row(
                "SELECT COALESCE(MAX(user_id) + 1, 1) user_id_ FROM users "
                "WHERE user_id < 100000 LIMIT 1;"
            )
        ).user_id_
        await itx.client.database.set(
            "INSERT INTO users (user_id, nickname) VALUES ($1, $2);",
            value,
            fake_user,
        )
        itx.client.cache.users.add_one(
            utils.UserData(
                user_id=value,
                nickname=fake_user,
                flags=utils.SettingFlags.NONE.value,
                is_creator=True,
            )
        )

    @mod_commands.command(name="link-member")
    @app_commands.autocomplete(fake_user=utils.autocomplete.users_autocomplete)
    async def link_member(
        self,
        itx: discord.Interaction[core.Genji],
        fake_user: str,
        member: discord.Member,
    ):
        """
        Link a fake user to a server member.

        Args:
            itx: Discord itx
            fake_user: The fake user
            member: The real user
        """
        await itx.response.defer(ephemeral=True)
        try:
            fake_user = int(fake_user)
        except ValueError:
            raise utils.InvalidFakeUser
        if fake_user >= 100000:
            raise utils.InvalidFakeUser
        fake_name = await itx.client.database.get_row(
            "SELECT * FROM users WHERE user_id=$1", fake_user
        )
        if not fake_name:
            raise utils.InvalidFakeUser

        view = views.Confirm(itx, ephemeral=True)
        await itx.edit_original_response(
            content=f"Link {fake_name.nickname} to {member.mention}?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await self.link_fake_to_member(itx, fake_user, member)

    @staticmethod
    async def link_fake_to_member(
        itx: discord.Interaction[core.Genji], fake_id: int, member: discord.Member
    ):
        await itx.client.database.set(
            "UPDATE map_creators SET user_id=$2 WHERE user_id=$1", fake_id, member.id
        )
        await itx.client.database.set(
            "UPDATE map_ratings SET user_id=$2 WHERE user_id=$1", fake_id, member.id
        )
        await itx.client.database.set(
            "DELETE FROM users WHERE user_id=$1",
            fake_id,
        )
        itx.client.cache.users[fake_id].update_user_id(member.id)


async def setup(bot: core.Genji):
    await bot.add_cog(ModCommands(bot))
