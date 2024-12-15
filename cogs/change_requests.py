from __future__ import annotations

import traceback
import typing

import discord.ui
from discord import Guild, Interaction
from discord.app_commands import Transform, autocomplete, command, guilds
from discord.ext import commands
from typing_extensions import TypeAlias

from utils import constants, records
from utils.transformers import map_codes_autocomplete

if typing.TYPE_CHECKING:
    from core import Genji
    from database import Database

    GenjiItx: TypeAlias = Interaction[Genji]


async def _get_map_creators(db: Database, map_code: str) -> list[int]:
    query = """
        SELECT array_agg(user_id)
        FROM map_creators
        WHERE map_code = $1
        GROUP BY map_code;
    """
    return await db.fetchval(query, map_code)


def _convert_ids_to_mentions(ids: list[int], guild: Guild) -> str:
    mentions = []
    fake_user_limit = 100000
    for id_ in ids:
        member = guild.get_member(id_) if id_ > fake_user_limit else None
        if member:
            mentions.append(member.mention)
    return " ".join(mentions)


class ChangeRequestModal(discord.ui.Modal):
    def __init__(self, map_code: str) -> None:
        super().__init__(title="Change Request", timeout=600)
        self.map_code = map_code

    feedback = discord.ui.TextInput(
        label="What change are you requesting?",
        style=discord.TextStyle.long,
        placeholder="Type your feedback here and please be specific.",
    )

    async def on_submit(self, itx: GenjiItx) -> None:
        await itx.response.send_message("Submitted.", ephemeral=True)
        assert itx.guild
        channel = itx.guild.get_channel(1316560101360013443)
        assert isinstance(channel, discord.TextChannel)
        user_ids = await _get_map_creators(itx.client.database, self.map_code)
        mentions = _convert_ids_to_mentions(user_ids, itx.guild)
        if not mentions:
            mentions = "<@1120076555293569081>\n-# The creator of this map is not in this server."
        message = (
            f"{mentions}\n"
            f"{itx.user.mention} is requesting changes for map **{self.map_code}**\n"
            f"{self.feedback.value}"
        )
        await channel.send(message)

    async def on_error(self, itx: GenjiItx, error: Exception) -> None:
        await itx.response.send_message("Oops! Something went wrong.", ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)


class ChangeRequestConfirmationView(discord.ui.View):
    def __init__(self, user_ids: list[int]) -> None:
        super().__init__(timeout=None)
        self.user_ids = user_ids

    async def interaction_check(self, itx: GenjiItx) -> bool:
        assert itx.guild and isinstance(itx.user, discord.Member)
        sensei = itx.guild.get_role(842790097312153610)
        moderator = itx.guild.get_role(1128014001318666423)
        return itx.user.id in self.user_ids or sensei in itx.user.roles or moderator in itx.user.roles

    @discord.ui.button(label="Confirm Map Change?", style=discord.ButtonStyle.green)
    async def confirmation_button(self, itx: GenjiItx, button: discord.ui.Button) -> None:
        button.label = "Confirmed"
        button.disabled = True
        await itx.response.edit_message(view=self)
        await itx.followup.send(f"{itx.user.mention} has confirmed that the map has ben changed as requested.")


class ChangeRequests(commands.Cog):
    def __init__(self, bot: Genji) -> None:
        self.bot = bot
        self.db = bot.database

    @command()
    @guilds(constants.GUILD_ID)
    @autocomplete(map_code=map_codes_autocomplete)
    async def change_request(
        self,
        itx: GenjiItx,
        map_code: Transform[str, records.MapCodeTransformer],
    ) -> None:
        await itx.response.send_modal(ChangeRequestModal(map_code))


async def setup(bot: Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(ChangeRequests(bot))
