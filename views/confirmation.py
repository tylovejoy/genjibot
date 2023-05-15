from __future__ import annotations

import copy
import datetime
import typing
from typing import TYPE_CHECKING

import discord

import utils
import views

if TYPE_CHECKING:
    import core


class ConfirmButton(discord.ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            label="Yes, the information I have entered is correct.",
            emoji=utils.CONFIRM_EMOJI,
            style=discord.ButtonStyle.green,
            disabled=disabled,
        )

    async def callback(self, itx: discord.Interaction[core.Genji]):
        """Confirmation button callback."""
        if self.view.original_itx.user != itx.user:
            # await itx.response.send_message(
            #     "You are not allowed to confirm this submission.",
            #     ephemeral=True,
            # )
            return
        self.view.value = True
        self.view.clear_items()
        # self.view.stop()
        await self.view.original_itx.edit_original_response(
            content=self.view.confirm_msg, view=self.view
        )
        self.view.stop()


class RejectButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="No, the information I have entered is not correct.",
            emoji=utils.UNVERIFIED_EMOJI,
            style=discord.ButtonStyle.red,
        )

    async def callback(self, itx: discord.Interaction[core.Genji]):
        """Rejection button callback."""
        await itx.response.defer(ephemeral=True)
        if self.view.original_itx.user != itx.user:
            # await itx.response.send_message(
            #     "You are not allowed to reject this submission.",
            #     ephemeral=True,
            # )
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
    difficulty: views.DifficultySelect | None
    restrictions: views.RestrictionsSelect | None
    map_type: views.MapTypeSelect | None
    mechanics: views.MechanicsSelect | None

    def __init__(
        self,
        original_itx: discord.Interaction[core.Genji],
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
            ],
            placeholder="Rate the quality of the map!",
        )

    async def callback(self, interaction: discord.Interaction[core.Genji]):
        await interaction.response.defer(ephemeral=True)
        await self.view.enable_submit()


class ConfirmCompletion(discord.ui.View):
    def __init__(
        self,
        rank: int,
        original_itx: discord.Interaction[core.Genji],
        confirm_msg="Confirmed.",
        ephemeral=False,
    ):
        super().__init__(timeout=None)
        self.rank = rank
        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None
        self.ephemeral = ephemeral

        # if self.rank > 5:
        #     self.quality = QualitySelect()
        #     self.add_item(self.quality)

        # self.confirm = ConfirmButton(disabled=self.rank > 5)
        self.confirm = ConfirmButton()
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
        original_itx: discord.Interaction[core.Genji],
        confirm_msg="Confirmed.",
    ):
        super().__init__(timeout=None)
        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None

        self.confirm = ConfirmButton()
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)


class ButtonBase(discord.ui.Button):
    view: ConfirmBaseView

    def __init__(self, value: bool, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    async def callback(self, itx: discord.Interaction[core.Genji]):
        await itx.response.defer(ephemeral=True)
        if self.view.itx.user != itx.user:
            await itx.followup.send(
                "You are not allowed to use this button.", ephemeral=True
            )
            return

        self.view.value = self.value
        self.view.clear_items()

        if not self.view.value:
            self.view.confirmation_message = (
                "Not confirmed. "
                "This message will delete in "
                f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
            )

        await self.view.itx.edit_original_response(
            content=self.view.confirmation_message, view=self.view
        )
        if not self.view.value:
            await utils.delete_interaction(self.view.itx, minutes=1)
        self.view.stop()


class BaseConfirmButton(ButtonBase):
    def __init__(self, disabled: bool):
        super().__init__(
            label="Yes, the information I have entered is correct.",
            emoji=utils.CONFIRM_EMOJI,
            style=discord.ButtonStyle.green,
            disabled=disabled,
            value=True,
            row=4,
        )


class BaseRejectButton(ButtonBase):
    def __init__(self):
        super().__init__(
            label="No, the information I have entered is not correct.",
            emoji=utils.UNVERIFIED_EMOJI,
            style=discord.ButtonStyle.red,
            value=False,
            row=4,
        )


class ConfirmBaseView(discord.ui.View):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback,
        *,
        initial_message="Confirm?",
        confirmation_message="Confirmed.",
        timeout=300,
    ):
        super().__init__(timeout=timeout)
        self.confirm_button = BaseConfirmButton(disabled=False)
        self.reject_button = BaseRejectButton()
        self.add_item(self.confirm_button)
        self.add_item(self.reject_button)
        self.itx = itx
        self.partial_callback = partial_callback
        self.initial_message = initial_message + self._get_timeout_message()
        self.confirmation_message = confirmation_message
        self.value = None

    def _get_timeout_message(self):
        view_expires_at = self.itx.created_at + datetime.timedelta(seconds=self.timeout)
        formatted_timestamp = discord.utils.format_dt(view_expires_at, style="R")
        return f"\n\nThis form will timeout {formatted_timestamp}."

    async def _respond(
        self,
        embed: discord.Embed = None,
        attachment: discord.Attachment | discord.File = None,
    ):
        if attachment is not None:
            attachment = [attachment]
        else:
            attachment = discord.utils.MISSING
        if self.itx.response.is_done():
            await self.itx.edit_original_response(
                content=self.initial_message,
                view=self,
                embed=embed,
                attachments=attachment,
            )
        else:
            await self.itx.response.send_message(
                content=self.initial_message,
                view=self,
                embed=embed,
                files=attachment,
                ephemeral=True,
            )

    async def start(
        self,
        embed: discord.Embed = None,
        attachment: discord.Attachment | discord.File = None,
    ):
        await self._respond(embed, attachment)
        await self.wait()

        if not self.value:
            return

        await discord.utils.maybe_coroutine(self.partial_callback)

    async def map_submit_enable(self):
        return True


class ConfirmMechanicsMixin(ConfirmBaseView):
    mechanics: views.MechanicsSelect

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mechanics = views.MechanicsSelect(
            copy.deepcopy(self.itx.client.cache.map_mechanics.options)
        )
        self.add_item(self.mechanics)


class ConfirmRestrictionsMixin(ConfirmBaseView):
    restrictions: views.RestrictionsSelect

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.restrictions = views.RestrictionsSelect(
            copy.deepcopy(self.itx.client.cache.map_restrictions.options)
        )
        self.add_item(self.restrictions)


class ConfirmMapTypeMixin(ConfirmBaseView):
    map_type: views.MapTypeSelect

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_type = views.MapTypeSelect(
            copy.deepcopy(self.itx.client.cache.map_types.options)
        )
        self.add_item(self.map_type)

    async def map_submit_enable(self):
        return await super().map_submit_enable() and self.map_type.values


class ConfirmDifficultyMixin(ConfirmBaseView):
    difficulty: views.DifficultySelect

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.difficulty = views.DifficultySelect(
            [discord.SelectOption(label=x, value=x) for x in utils.DIFFICULTIES_EXT]
        )
        self.add_item(self.difficulty)

    async def map_submit_enable(self):
        return await super().map_submit_enable() and self.difficulty.values


class ConfirmMapSubmission(
    ConfirmMechanicsMixin,
    ConfirmRestrictionsMixin,
    ConfirmMapTypeMixin,
    ConfirmDifficultyMixin,
):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback,
        *,
        initial_message="Confirm?",
        confirmation_message="Confirmed.",
        timeout=300,
    ):
        super().__init__(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )
        self.confirm_button.disabled = True

    async def map_submit_enable(self):
        if await super().map_submit_enable():
            self.confirm_button.disabled = False
            await self.itx.edit_original_response(view=self)


class ConfirmMechanics(ConfirmMechanicsMixin):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback,
        *,
        initial_message="Confirm?",
        confirmation_message="Confirmed.",
        timeout=300,
    ):
        super().__init__(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )


class ConfirmRestrictions(ConfirmRestrictionsMixin):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback,
        *,
        initial_message="Confirm?",
        confirmation_message="Confirmed.",
        timeout=300,
    ):
        super().__init__(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )


class ConfirmDifficulty(ConfirmDifficultyMixin):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback,
        *,
        initial_message="Confirm?",
        confirmation_message="Confirmed.",
        timeout=300,
    ):
        super().__init__(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )


class ConfirmMapType(ConfirmMapTypeMixin):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback,
        *,
        initial_message="Confirm?",
        confirmation_message="Confirmed.",
        timeout=300,
    ):
        super().__init__(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )


class GiveReasonModalButton(discord.ui.Button):
    view: Confirm
    value: str

    def __init__(self):
        super().__init__(
            label="Give Reason",
            style=discord.ButtonStyle.blurple,
        )

    async def callback(self, itx: discord.Interaction[core.Genji]):
        modal = GiveReasonModal()
        await itx.response.send_modal(modal)
        await modal.wait()
        if not modal.value:
            return
        self.view.confirm.disabled = False
        await self.view.original_itx.edit_original_response(view=self.view)
        self.value = modal.reason.value


class GiveReasonModal(discord.ui.Modal, title="Give Reason"):
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Give a reason for denial.",
        style=discord.TextStyle.long,
    )
    value: bool = False

    async def on_submit(self, itx: discord.Interaction[core.Genji]):
        await itx.response.defer(ephemeral=True)
        self.value = True
