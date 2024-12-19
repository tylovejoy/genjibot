from __future__ import annotations

import contextlib
import datetime
import logging
from typing import TYPE_CHECKING, Callable

import discord

import views
from utils import constants, ranks, utils

if TYPE_CHECKING:
    import core

log = logging.getLogger(__name__)

class ConfirmButton(discord.ui.Button):
    def __init__(self, disabled: bool = False) -> None:
        super().__init__(
            label="Yes, the information I have entered is correct.",
            emoji=constants.CONFIRM_EMOJI,
            style=discord.ButtonStyle.green,
            disabled=disabled,
        )

    async def callback(self, itx: discord.Interaction[core.Genji]) -> None:
        """Confirm button callback."""
        if self.view.original_itx.user != itx.user:
            return
        self.view.value = True
        self.view.clear_items()
        with contextlib.suppress(discord.HTTPException):
            await self.view.original_itx.edit_original_response(content=self.view.confirm_msg, view=self.view)
        self.view.stop()


class RejectButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="No, the information I have entered is not correct.",
            emoji=constants.UNVERIFIED_EMOJI,
            style=discord.ButtonStyle.red,
        )

    async def callback(self, itx: discord.Interaction[core.Genji]) -> None:
        """Rejection button callback."""
        await itx.response.defer(ephemeral=True)
        if self.view.original_itx.user != itx.user:
            return
        self.view.value = False
        self.view.clear_items()
        content = (
            "Not confirmed. "
            "This message will delete in "
            f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
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
        confirm_msg: str = "Confirmed.",
        proceeding_items: dict[str, discord.ui.Item] | None = None,
        ephemeral: bool = False,
    ) -> None:
        super().__init__()

        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None
        self.ephemeral = ephemeral

        if proceeding_items:
            for attr, item in proceeding_items.items():
                setattr(self, attr, item)
                self.add_item(getattr(self, attr))

        self.confirm = ConfirmButton(disabled=bool(proceeding_items))
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)

    async def map_submit_enable(self) -> None:
        values = [getattr(getattr(self, x, None), "values", True) for x in ["map_type", "difficulty"]]
        if all(values):
            self.confirm.disabled = False
            await self.original_itx.edit_original_response(view=self)


class QualitySelect(discord.ui.Select):
    view: ConfirmCompletion

    def __init__(self) -> None:
        super().__init__(
            options=[
                discord.SelectOption(
                    label=constants.ALL_STARS[x - 1],
                    value=str(x),
                )
                for x in range(1, 7)
            ],
            placeholder="Rate the quality of the map!",
        )

    async def callback(self, interaction: discord.Interaction[core.Genji]) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.view.enable_submit()


class ConfirmCompletion(discord.ui.View):
    def __init__(
        self,
        original_itx: discord.Interaction[core.Genji],
        confirm_msg: str = "Confirmed.",
        ephemeral: bool = False,
    ) -> None:
        super().__init__(timeout=3600)
        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None
        self.ephemeral = ephemeral

        self.confirm = ConfirmButton()
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)

    async def enable_submit(self) -> None:
        self.confirm.disabled = False
        for o in self.quality.options:
            o.default = o.value in self.quality.values
        await self.original_itx.edit_original_response(view=self)


class RecordVideoConfirmCompletion(discord.ui.View):
    def __init__(
        self,
        original_itx: discord.Interaction[core.Genji],
        confirm_msg: str = "Confirmed.",
    ) -> None:
        super().__init__(timeout=3600)
        self.original_itx = original_itx
        self.confirm_msg = confirm_msg
        self.value = None

        self.confirm = ConfirmButton()
        self.reject = RejectButton()
        self.add_item(self.confirm)
        self.add_item(self.reject)


class ButtonBase(discord.ui.Button):
    view: ConfirmBaseView

    def __init__(self, value: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self.value = value

    async def callback(self, itx: discord.Interaction[core.Genji]) -> None:
        await itx.response.defer(ephemeral=True)
        if self.view.itx.user != itx.user:
            await itx.followup.send("You are not allowed to use this button.", ephemeral=True)
            return

        self.view.value = self.value
        self.view.clear_items()

        if not self.view.value:
            self.view.confirmation_message = (
                "Not confirmed. "
                "This message will delete in "
                f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
            )

        await self.view.itx.edit_original_response(content=self.view.confirmation_message, view=self.view)
        if not self.view.value:
            await utils.delete_interaction(self.view.itx, minutes=1)
        self.view.stop()


class BaseConfirmButton(ButtonBase):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label="Yes, the information I have entered is correct.",
            emoji=constants.CONFIRM_EMOJI,
            style=discord.ButtonStyle.green,
            disabled=disabled,
            value=True,
            row=4,
        )


class BaseRejectButton(ButtonBase):
    def __init__(self) -> None:
        super().__init__(
            label="No, the information I have entered is not correct.",
            emoji=constants.UNVERIFIED_EMOJI,
            style=discord.ButtonStyle.red,
            value=False,
            row=4,
        )


class ConfirmBaseView(discord.ui.View):
    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback: Callable,
        *,
        initial_message: str = "Confirm?",
        confirmation_message: str = "Confirmed.",
        timeout: int = 300,
    ) -> None:
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

    def _get_timeout_message(self) -> str:
        view_expires_at = self.itx.created_at + datetime.timedelta(seconds=self.timeout)
        formatted_timestamp = discord.utils.format_dt(view_expires_at, style="R")
        return f"\n\nThis form will timeout {formatted_timestamp}."

    async def _respond(
        self,
        embed: discord.Embed = None,
        attachment: discord.Attachment | discord.File = None,
    ) -> None:
        attachment = [attachment] if attachment is not None else discord.utils.MISSING

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
    ) -> None:
        await self._respond(embed, attachment)
        await self.wait()

        if not self.value:
            return

        await discord.utils.maybe_coroutine(self.partial_callback)


class ConfirmMapSubmission(ConfirmBaseView):
    difficulty: views.DifficultySelect
    map_type: views.MapTypeSelect
    restrictions: views.RestrictionsSelect
    mechanics: views.MechanicsSelect

    def __init__(
        self,
        itx: discord.Interaction[core.Genji],
        partial_callback: Callable,
        *,
        initial_message: str = "Confirm?",
        confirmation_message: str = "Confirmed.",
        timeout: int = 300,
    ) -> None:
        super().__init__(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )
        self.confirm_button.disabled = True

    @classmethod
    async def async_build(
        cls,
        itx: discord.Interaction[core.Genji],
        partial_callback: Callable,
        *,
        initial_message: str = "Confirm?",
        confirmation_message: str = "Confirmed.",
        timeout: int = 300,  # noqa: ASYNC109
    ) -> ConfirmMapSubmission:
        inst = cls(
            itx,
            partial_callback,
            initial_message=initial_message,
            confirmation_message=confirmation_message,
            timeout=timeout,
        )
        select_map = [
            ("map_type", views.MapTypeSelect),
            ("mechanics", views.MechanicsSelect),
            ("restrictions", views.RestrictionsSelect),
        ]

        for type_, select_cls in select_map:
            options = await utils.db_records_to_options(itx.client.database, type_)
            select = select_cls(options)
            setattr(inst, type_, select)
            inst.add_item(select)

        difficulty_options = [discord.SelectOption(label=x, value=x) for x in ranks.DIFFICULTIES_EXT[1:]]
        inst.difficulty = views.DifficultySelect(difficulty_options)
        inst.add_item(inst.difficulty)

        return inst

    async def map_submit_enable(self) -> None:
        if self.difficulty.values and self.map_type.values:
            self.confirm_button.disabled = False
            await self.itx.edit_original_response(view=self)
