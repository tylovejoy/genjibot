from __future__ import annotations

import contextlib
import logging
import re
import traceback
import typing

import discord.ui
from discord import Guild, Interaction
from discord.app_commands import Transform, command, guilds
from discord.ext import commands
from typing_extensions import TypeAlias

from utils import constants, transformers

if typing.TYPE_CHECKING:
    from core import Genji
    from database import Database

    GenjiItx: TypeAlias = Interaction[Genji]


log = logging.getLogger(__name__)


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
            mentions = "<@&1120076555293569081>\n-# The creator of this map is not in this server."
        content = (
            f"# {mentions}\n\n"
            f"## {itx.user.mention} is requesting changes for map **{self.map_code}**\n\n"
            f"{self.feedback.value}"
        )
        view = ChangeRequestConfirmationView(user_ids, self.map_code)
        message = await channel.send(content)
        thread = await message.create_thread(name=f"CR-{self.map_code} Discussion")
        await thread.send(
            content=f"# {mentions}\n# If you have made the necessary changes, please click the button to confirm.",
            view=view,
        )

    async def on_error(self, itx: GenjiItx, error: Exception) -> None:
        await itx.response.send_message("Oops! Something went wrong.", ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)


class ChangeRequestConfirmationView(discord.ui.View):
    def __init__(self, user_ids: list[int], map_code: str) -> None:
        super().__init__(timeout=None)
        self.user_ids = user_ids
        self.confirm_button = ChangeRequestConfirmationButton(user_ids, map_code)
        self.add_item(self.confirm_button)


class ChangeRequestCloseView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def interaction_check(self, itx: GenjiItx, /) -> bool:
        assert itx.guild and isinstance(itx.user, discord.Member)
        sensei = itx.guild.get_role(842790097312153610)
        moderator = itx.guild.get_role(1128014001318666423)
        return sensei in itx.user.roles or moderator in itx.user.roles

    @discord.ui.button(
        label="Close (Sensei Only)",
        style=discord.ButtonStyle.red,
        custom_id="CR-Close",
        row=1,
        emoji="\N{HEAVY MULTIPLICATION X}",
    )
    async def callback(self, itx: GenjiItx, button: discord.ui.Button) -> None:
        await itx.response.defer(ephemeral=True)
        thread = itx.channel
        assert isinstance(thread, discord.Thread)
        await thread.edit(archived=True, locked=True)
        original_message = thread.starter_message
        if not original_message:
            assert thread.starter_message and itx.guild
            change_channel = itx.guild.get_channel(1316560101360013443)
            assert isinstance(change_channel, discord.TextChannel) and itx.channel
            original_message = await change_channel.fetch_message(itx.channel.id)
        embed = discord.Embed(description="Original Message:\n\n" + original_message.content)
        with contextlib.suppress(Exception):
            await thread.send(embed=embed)
            await original_message.delete()


class ChangeRequestConfirmationButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"CRC-(?P<map_code>[A-Z0-9]{4,6})-(?P<id0>[0-9]+)-?(?P<id1>[0-9]+)?-?(?P<id2>[0-9]+)?-?(?P<id3>[0-9]+)?",
):
    def __init__(self, user_ids: list[int], map_code: str) -> None:
        custom_id = "-".join(["CRC", map_code, *map(str, user_ids)])
        super().__init__(
            discord.ui.Button(
                label="Confirm Map Has Been Changed?",
                style=discord.ButtonStyle.green,
                custom_id=custom_id,
                emoji="\N{THUMBS UP SIGN}",
            )
        )
        self.user_ids = user_ids
        self.map_code = map_code

    @classmethod
    async def from_custom_id(
        cls, itx: GenjiItx, item: discord.ui.Button, match: re.Match[str]
    ) -> ChangeRequestConfirmationButton:
        ids = []
        for i in range(4):
            m = match["id" + str(i)]
            if m:
                ids.append(int(match["id" + str(i)]))
        return cls(ids, match["map_code"])

    async def interaction_check(self, itx: GenjiItx) -> bool:
        assert itx.guild and isinstance(itx.user, discord.Member)
        sensei = itx.guild.get_role(842790097312153610)
        moderator = itx.guild.get_role(1128014001318666423)
        return itx.user.id in self.user_ids or sensei in itx.user.roles or moderator in itx.user.roles

    async def callback(self, itx: GenjiItx) -> None:
        self.item.label = "Confirmed"
        self.item.disabled = True
        await itx.response.edit_message(view=self.view)
        assert itx.guild
        modmail = itx.guild.get_role(1120076555293569081)
        assert modmail and isinstance(itx.channel, discord.Thread)
        await itx.channel.send(
            f"{itx.user.mention} has confirmed that the map has been changed as requested. {modmail.mention}",
            view=ChangeRequestCloseView(),
        )


class ChangeRequests(commands.Cog):
    def __init__(self, bot: Genji) -> None:
        self.bot = bot
        self.db = bot.database

    @command(name="change-request")
    @guilds(constants.GUILD_ID)
    async def change_request(
        self,
        itx: GenjiItx,
        map_code: Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        await itx.response.send_modal(ChangeRequestModal(map_code))


async def setup(bot: Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(ChangeRequests(bot))
    bot.add_dynamic_items(ChangeRequestConfirmationButton)
    bot.add_view(ChangeRequestCloseView())
