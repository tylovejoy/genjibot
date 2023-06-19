from __future__ import annotations

import copy
import datetime
from typing import TYPE_CHECKING

import discord

from utils import (
    DIFFICULTIES_EXT,
    MapSubmission,
    GenjiEmbed,
    set_embed_thumbnail_maps,
    delete_interaction,
    PLAYTEST,
    MapData,
    Roles,
    new_map_newsfeed,
    BaseMapData,
)
from views import PlaytestVoting

if TYPE_CHECKING:
    import core

_difficulty_options = [discord.SelectOption(label=x, value=x) for x in DIFFICULTIES_EXT]


class MapSubmissionView(discord.ui.View):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        initial_message: str,
        data: MapSubmission,
        is_mod: bool,
    ):
        super().__init__(timeout=600)
        self.itx = itx
        self.initial_message = initial_message + self._get_timeout_message()
        self.confirmation_message = "Confirmed"
        self.value = None
        self.data = data
        self.is_mod = is_mod
        self._setup_selects()
        self.embed = self._init_embed()

    def _get_timeout_message(self):
        view_expires_at = self.itx.created_at + datetime.timedelta(seconds=self.timeout)
        formatted_timestamp = discord.utils.format_dt(view_expires_at, style="R")
        return f"\n\nThis form will timeout {formatted_timestamp}."

    def _setup_selects(self):
        self._set_select_options(
            self.mechanics, self.itx.client.cache.map_mechanics.options
        )
        self._set_select_options(
            self.restrictions, self.itx.client.cache.map_restrictions.options
        )
        self._set_select_options(self.map_type, self.itx.client.cache.map_types.options)
        self.difficulty.options = copy.deepcopy(_difficulty_options)

    @staticmethod
    def _set_select_options(
        select: discord.ui.Select, options: list[discord.SelectOption]
    ):
        select.options = copy.deepcopy(options)
        select.max_values = len(options)

    @discord.ui.select(min_values=0, placeholder="Mechanics")
    async def mechanics(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        await itx.response.defer(ephemeral=True)
        self._keep_options_selected(select)
        self.data.mechanics = select.values
        await self._refresh_view()

    @discord.ui.select(min_values=0, placeholder="Restrictions")
    async def restrictions(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        await itx.response.defer(ephemeral=True)
        self._keep_options_selected(select)
        self.data.restrictions = select.values
        await self._refresh_view()

    @discord.ui.select(placeholder="Map Type")
    async def map_type(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        await itx.response.defer(ephemeral=True)
        self._keep_options_selected(select)
        self.data.map_types = select.values
        await self._refresh_view()

    @discord.ui.select(
        options=[discord.SelectOption(label=x, value=x) for x in DIFFICULTIES_EXT],
        placeholder="Difficulty",
    )
    async def difficulty(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        await itx.response.defer(ephemeral=True)
        self._keep_options_selected(select)
        self.data.difficulty = select.values[0]
        await self._refresh_view()

    async def _button(self, itx: discord.Interaction[core.Genji], value: bool):
        await itx.response.defer(ephemeral=True)
        if self.itx.user != itx.user:
            await itx.followup.send(
                "You are not allowed to use this button.", ephemeral=True
            )
            return
        self.value = value
        self.clear_items()
        if not self.value:
            self.confirmation_message = (
                "Not confirmed. "
                "This message will delete in "
                f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
            )

        await self.itx.edit_original_response(
            content=self.confirmation_message, view=self
        )
        if not self.value:
            await delete_interaction(self.itx, minutes=1)
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, disabled=True)
    async def confirm(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        await self._button(itx, True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        await self._button(itx, False)

    @staticmethod
    def _keep_options_selected(select: discord.ui.Select):
        for x in select.options:
            x.default = x.value in select.values

    def _check_confirm_enablement(self):
        return self.data.map_types and self.data.difficulty

    async def _refresh_view(self):
        self.embed.description = str(self.data)
        if self._check_confirm_enablement():
            self.confirm.disabled = False
        await self.itx.edit_original_response(embed=self.embed, view=self)

    def _init_embed(self):
        embed = GenjiEmbed(
            title="Map Submission",
            description=str(self.data),
        )
        embed.set_author(
            name=self.itx.client.cache.users[self.data.creator.id].nickname,
            icon_url=self.data.creator.display_avatar.url,
        )
        embed = set_embed_thumbnail_maps(self.data.map_name, embed)
        return embed

    async def _post_to_playtest(self):
        self.embed.title = "Calling all Playtesters!"
        view = PlaytestVoting(
            self.data,
            self.itx.client,
        )
        playtest_message = await self.itx.guild.get_channel(PLAYTEST).send(
            content=f"Total Votes: 0 / {view.required_votes}", embed=self.embed
        )
        embed = GenjiEmbed(
            title="Difficulty Ratings",
            description="You can change your vote, but you cannot cast multiple!\n\n",
        )
        thread = await playtest_message.create_thread(
            name=(
                f"{self.data.map_code} | {self.data.difficulty} | {self.data.map_name} "
                f"{self.data.checkpoint_count} CPs"
            )
        )

        thread_msg = await thread.send(
            f"Discuss, play, rate, etc.",
            view=view,
            embed=embed,
        )
        self.itx.client.playtest_views[thread_msg.id] = view
        await thread.send(
            f"{self.itx.user.mention}, you can receive feedback on your map here. "
            f"I'm pinging you so you are able to join this thread automatically!"
        )

        await self.data.insert_playtest(
            self.itx, thread.id, thread_msg.id, playtest_message.id
        )

    async def start(self):
        await self.itx.edit_original_response(
            content=self.initial_message, embed=self.embed, view=self
        )
        await self.wait()
        if not self.value:
            return

        if not self.is_mod:
            await self._post_to_playtest()

        await self.data.insert_all(self.itx, self.is_mod)
        self.itx.client.cache.maps.add_one(
            MapData(
                map_code=self.data.map_code,
                user_ids=[self.data.creator.id],
                archived=False,
            )
        )
        if not self.is_mod:
            map_maker = self.itx.guild.get_role(Roles.MAP_MAKER)
            if map_maker not in self.itx.user.roles:
                await self.itx.user.add_roles(map_maker, reason="Submitted a map.")
        else:
            await new_map_newsfeed(self.itx.client, self.data.creator.id, self.data)
        if not self.itx.client.cache.users.find(self.data.creator.id).is_creator:
            self.itx.client.cache.users.find(self.data.creator.id).update_is_creator(
                True
            )
