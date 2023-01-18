from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import utils

if typing.TYPE_CHECKING:
    import core


class Personal(commands.Cog):
    @app_commands.command(name="name")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def nickname_change(
        self,
        itx: core.Interaction[core.Genji],
        nickname: app_commands.Range[str, 1, 25],
    ) -> None:
        """
        Change your display name in bot commands.

        Args:
            itx: Interaction
            nickname: New nickname
        """
        await itx.response.send_message(
            f"Changing your nick name from {itx.client.all_users[itx.user.id]['nickname']} to {nickname}"
        )
        await itx.client.database.set(
            "UPDATE users SET nickname=$2 WHERE user_id=$1",
            itx.user.id,
            nickname,
        )
        itx.client.all_users[itx.user.id]["nickname"] = nickname


async def setup(bot: core.Genji):
    await bot.add_cog(Personal(bot))
