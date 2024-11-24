from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import views
from utils import constants, embeds, errors, utils

if typing.TYPE_CHECKING:
    import core


class Tags(commands.GroupCog, group_name="tag"):
    @app_commands.command()
    @app_commands.autocomplete(name=cogs.tags_autocomplete)
    @app_commands.checks.cooldown(3, 30, key=lambda i: (i.guild_id, i.user.id))
    async def view(
        self,
        itx: discord.Interaction[core.Genji],
        name: str,
    ) -> None:
        """View a tag."""
        await itx.response.defer()
        if name not in itx.client.cache.tags.list:
            fuzzed_options = utils.fuzz_multiple(name, itx.client.cache.tags.list)
            fuzz_desc = [f"{views.NUMBER_EMOJI[i + 1]} - {x}\n" for i, x in enumerate(fuzzed_options)]

            embed = embeds.GenjiEmbed(
                title="Tags",
                description=(f"Couldn't find `{name}`. Did you mean:\n" + "".join(fuzz_desc)),
            )
            view = views.TagFuzzView(itx, fuzzed_options)
            await itx.edit_original_response(embed=embed, view=view)
            await view.wait()

            return

        query = "SELECT * FROM tags WHERE name = $1;"
        row = await itx.client.database.fetchrow(query, name)
        if row is None:
            raise ValueError
        await itx.edit_original_response(content=discord.utils.escape_mentions(f"**{row['name']}**\n\n{row['value']}"))

    @app_commands.command()
    async def create(self, itx: discord.Interaction[core.Genji]) -> None:
        """Create a tag."""
        if (
            itx.guild.get_role(constants.TAG_MAKER) not in itx.user.roles
            and itx.guild.get_role(constants.STAFF) not in itx.user.roles
        ):
            raise errors.NoPermissionsError
        modal = views.TagCreate()
        await itx.response.send_modal(modal)


async def setup(bot: core.Genji) -> None:
    """Add cog to bot."""
    await bot.add_cog(Tags(bot), guilds=[discord.Object(id=constants.GUILD_ID)])
