from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import discord

import utils
import views

if TYPE_CHECKING:
    import core


class ConfirmButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            label="Yes, the information entered is correct.",
            emoji=utils.CONFIRM_EMOJI,
            style=discord.ButtonStyle.green,
            disabled=disabled,
        )

    async def callback(self, itx: core.Interaction[core.Genji]):
        """Confirmation button callback."""
        if self.view.original_itx.user != itx.user:
            await itx.response.send_message(
                "You are not allowed to confirm this submission.",
                ephemeral=True,
            )
            return
        self.view.value = True
        self.view.clear_items()
        self.view.stop()
        await self.view.original_itx.edit_original_response(
            content=self.view.confirm_msg, view=self.view
        )


class RejectButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="No, the information entered is not correct.",
            emoji=utils.UNVERIFIED_EMOJI,
            style=discord.ButtonStyle.red,
        )

    async def callback(self, itx: core.Interaction[core.Genji]):
        """Rejection button callback."""
        await itx.response.defer(ephemeral=True)
        if self.view.original_itx.user != itx.user:
            await itx.response.send_message(
                "You are not allowed to reject this submission.",
                ephemeral=True,
            )
            return
        self.view.value = False
        self.view.clear_items()
        content = (
            "Not confirmed. "
            "This message will delete in "
            f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"  # noqa
        )
        await self.view.original_itx.edit_original_response(
            content=content,
            view=self.view,
        )
        await utils.delete_interaction(self.view.original_itx, minutes=1)
        self.view.stop()


class Confirm(discord.ui.View):
    difficulty: views.MapTypeSelect | None
    restrictions: views.RestrictionsSelect | None
    map_type: views.MapTypeSelect | None
    mechanics: views.MechanicsSelect | None

    def __init__(
        self,
        original_itx: core.Interaction[core.Genji],
        confirm_msg="Confirmed.",
        preceeding_items: dict[str, discord.ui.Item] | None = None,
        ephemeral=False,
    ):
        super().__init__()

        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None
        self.ephemeral = ephemeral

        if preceeding_items:
            for attr, item in preceeding_items.items():
                setattr(self, attr, item)
                self.add_item(getattr(self, attr))

        self.confirm = ConfirmButton(disabled=bool(preceeding_items))
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)

    async def map_submit_enable(self):
        values = [
            getattr(getattr(self, x, None), "values", True)
            for x in ["map_type", "difficulty"]
        ]
        if all(values):
            self.confirm.disabled = False
            await self.original_itx.edit_original_response(view=self)


class QualitySelect(discord.ui.Select):
    view: ConfirmCompletion

    def __init__(self):

        super().__init__(
            options=[
                discord.SelectOption(
                    label=utils.ALL_STARS[x - 1],
                    value=str(x),
                )
                for x in range(1, 7)
            ]
        )

    async def callback(self, interaction: core.Interaction[core.Genji]):
        await interaction.response.defer(ephemeral=True)
        await self.view.enable_submit()


class ConfirmCompletion(discord.ui.View):
    def __init__(
        self,
        rank: int,
        original_itx: core.Interaction[core.Genji],
        confirm_msg="Confirmed.",
        ephemeral=False,
    ):
        super().__init__()
        self.rank = rank
        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None
        self.ephemeral = ephemeral

        if self.rank > 5:
            self.quality = QualitySelect()
            self.add_item(self.quality)

        self.confirm = ConfirmButton(disabled=self.rank > 5)
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)

    async def enable_submit(self):
        self.confirm.disabled = False
        for o in self.quality.options:
            o.default = o.value in self.quality.values
        await self.original_itx.edit_original_response(view=self)


class RecordVideoConfirmCompletion(discord.ui.View):
    def __init__(
        self,
        original_itx: core.Interaction[core.Genji],
        confirm_msg="Confirmed.",
    ):
        super().__init__()
        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None

        self.confirm = ConfirmButton()
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)
