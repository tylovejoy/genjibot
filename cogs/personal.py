from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import views
from utils import constants

if typing.TYPE_CHECKING:
    import core


class Personal(commands.Cog):
    @app_commands.command()
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    async def settings(self, itx: discord.Interaction[core.Genji]):
        """Change various settings like notifications and your display name."""
        await itx.response.defer(ephemeral=True)
        data = await itx.client.database.get_row("SELECT flags FROM users WHERE user_id = $1", itx.user.id)
        flags = data.flags
        view = views.SettingsView(itx, flags)
        await itx.edit_original_response(view=view)


async def setup(bot: core.Genji):
    await bot.add_cog(Personal(bot))
