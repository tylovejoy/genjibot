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


class Tags(discord.ext.commands.GroupCog, group_name="tag"):
    """Tags"""

    @app_commands.command()
    @app_commands.autocomplete(name=cogs.tags_autocomplete)
    @app_commands.checks.cooldown(3, 30, key=lambda i: (i.guild_id, i.user.id))
    async def view(
        self,
        itx: core.Interaction[core.Genji],
        name: str,
    ) -> None:
        """View a tag."""
        await itx.response.defer()
        if name not in itx.client.tag_cache:
            fuzzed_options = utils.fuzz_multiple(name, itx.client.tag_cache)
            fuzz_desc = [
                f"{utils.NUMBER_EMOJI[i + 1]} - {x}\n"
                for i, x in enumerate(fuzzed_options)
            ]

            embed = utils.GenjiEmbed(
                title="Tags",
                description=(
                    f"Couldn't find `{name}`. Did you mean:\n" + "".join(fuzz_desc)
                ),
            )
            view = views.TagFuzzView(itx, fuzzed_options)
            await itx.edit_original_response(embed=embed, view=view)
            await view.wait()

            return

        tag = [
            x
            async for x in itx.client.database.get(
                "SELECT * FROM tags WHERE name=$1",
                name,
            )
        ][0]
        await itx.edit_original_response(
            content=discord.utils.escape_mentions(f"**{tag.name}**\n\n{tag.value}")
        )

    @app_commands.command()
    async def create(self, itx: core.Interaction[core.Genji]):
        """Create a tag"""
        if (
            itx.guild.get_role(utils.TAG_MAKER) not in itx.user.roles
            and itx.guild.get_role(utils.STAFF) not in itx.user.roles
        ):
            raise utils.NoPermissionsError
        modal = views.TagCreate()
        await itx.response.send_modal(modal)


async def setup(bot: core.Genji):
    await bot.add_cog(Tags(bot), guilds=[discord.Object(id=utils.GUILD_ID)])
