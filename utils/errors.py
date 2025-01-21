from __future__ import annotations

import datetime
import io
import re
import traceback
import typing

import discord
from discord import app_commands
from sentry_sdk import capture_exception

from utils import embeds, utils

if typing.TYPE_CHECKING:
    from core import Genji


class BaseParkourError(Exception):
    def __init__(self, additional_info: str = "") -> None:
        super().__init__(self.__doc__ + "\n" + additional_info)


class DatabaseConnectionError(Exception):
    """Connection failed. This will be logged. Try again later."""


class IncorrectRecordFormatError(BaseParkourError, app_commands.errors.AppCommandError):
    """Record must be in XXXX.xx format e.g. 1569.33, 567.01, 10.50, etc."""


class IncorrectCodeFormatError(BaseParkourError, app_commands.errors.AppCommandError):
    """Map code must be a valid Overwatch share code."""


class IncorrectURLFormatError(BaseParkourError, app_commands.errors.AppCommandError):
    """The given URL is invalid."""


class InvalidFiltersError(BaseParkourError):
    """You must choose _at least_ **one** filter
    (map name, map type, or creator, mechanics, official, difficulty).
    """  # noqa: D205


class InvalidMapNameError(BaseParkourError, app_commands.errors.AppCommandError):
    """Invalid map name given. Please make sure to use the autocompleted map names."""


class InvalidMapCodeError(BaseParkourError, app_commands.errors.AppCommandError):
    """Invalid map code given. Please make sure to use the autocompleted map codes."""


class InvalidMapLevelError(BaseParkourError, app_commands.errors.AppCommandError):
    """Invalid map level given. Please make sure to use the autocompleted map levels."""


class InvalidMapTypeError(BaseParkourError, app_commands.errors.AppCommandError):
    """Invalid map name given. Please make sure to use the autocompleted map types."""


class RecordNotFasterError(BaseParkourError, app_commands.errors.AppCommandError):
    """Record must be faster than your previous submission."""


class NoMapsFoundError(BaseParkourError, app_commands.errors.AppCommandError):
    """No maps have been found with the given filters."""


class NoRecordsFoundError(BaseParkourError, app_commands.errors.AppCommandError):
    """No records have been found."""


class NoCompletionFoundError(BaseParkourError):
    """You cannot rate a map without a completion."""


class CannotRateOwnMapError(BaseParkourError):
    """You cannot rate your own map."""


class NoPermissionsError(BaseParkourError, app_commands.errors.AppCommandError):
    """You do not have permission to do this action."""


class CreatorAlreadyExistsError(BaseParkourError):
    """Creator already associated with this map."""


class MaxMapsInPlaytestError(BaseParkourError):
    """You have reached the maximum total amount (5) of maps in playtest.
    Try to engage other members to playtest your map in order to get verified and submit more maps.
    """  # noqa: D205


class MaxWeeklyMapsInPlaytestError(BaseParkourError):
    """You have reached the maximum amount of maps (2) submitted within the last week.
    Focus on getting your maps verified before submitting more!
    """  # noqa: D205, D400


class CreatorDoesntExistError(BaseParkourError):
    """Creator is not associated with this map."""


class MapExistsError(BaseParkourError, app_commands.errors.AppCommandError):
    """This map code already exists!"""  # noqa: D400, D404


class NoGuidesExistError(BaseParkourError, app_commands.errors.AppCommandError):
    """No guides exist for this map code."""


class GuideExistsError(BaseParkourError, app_commands.errors.AppCommandError):
    """This guide has already been submitted."""  # noqa: D404


class OutOfRangeError(BaseParkourError, app_commands.errors.AppCommandError):
    """Choice is out of range."""


class InvalidIntegerError(BaseParkourError, app_commands.errors.AppCommandError):
    """Choice must be a valid integer."""


class UserNotFoundError(BaseParkourError, app_commands.errors.AppCommandError):
    """User does not exist."""


class FakeUserNotFoundError(BaseParkourError, app_commands.errors.AppCommandError):
    """Fake user does not exist."""


class RankTooLowError(BaseParkourError, app_commands.errors.AppCommandError):
    """Your rank is too low to do this action."""


class VideoNoRecordError(BaseParkourError, app_commands.errors.AppCommandError):
    """If you add a video, you must submit a time record as well. Please submit again with the `record` argument."""


class TemporaryMultiBanError(BaseParkourError, app_commands.errors.AppCommandError):
    """Recently an exploit for multiclimb has been going viral.
    We are forced to take some temporary measures to deal with this situation.
    For now, we are **NOT** verifying **ANY** completion for maps that allow multiclimbing.

    This means that for now **ONLY maps that have the multi banned will be verified.**
    """  # noqa: D205


class TemporaryHardOrHigherBanError(BaseParkourError, app_commands.errors.AppCommandError):
    """It's come to our attention that there is a new tech introduced in the new patch named "Save Double".

    This can potentially break many maps above Medium + and we are going to temporarily pause submissions for maps higher than Medium +.
    """  # noqa: E501


class InvalidFakeUserError(BaseParkourError, app_commands.errors.AppCommandError):
    """This fake user does not exist."""  # noqa: D404


class InvalidMedalsError(BaseParkourError, app_commands.errors.AppCommandError):
    """Medals are incorrectly formatted.
    Make sure gold is faster than silver and silver is faster than bronze.
    """  # noqa: D205


class ArchivedMapError(BaseParkourError, app_commands.errors.AppCommandError):
    """Map has been archived. Records cannot be submitted."""


class CannotVerifyOwnRecordsError(BaseParkourError, app_commands.errors.AppCommandError):
    """You cannot verify your own records/submissions."""


class WrongCompletionChannelError(BaseParkourError, app_commands.errors.AppCommandError):
    """You can only submit in <#1072898844339224627>."""


async def on_app_command_error(
    itx: discord.Interaction[Genji],
    error: app_commands.errors.CommandInvokeError | Exception,
) -> None:
    """Handle app command errors."""
    exception = getattr(error, "original", error)
    if isinstance(exception, BaseParkourError):
        embed = embeds.ErrorEmbed(description=str(exception))
        content = (
            "This message will delete in "
            f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
        )
        if itx.response.is_done():
            await itx.edit_original_response(
                content=content,
                embed=embed,
            )
        else:
            await itx.response.send_message(
                content=content,
                embed=embed,
                ephemeral=True,
            )
        await utils.delete_interaction(itx, minutes=1)

    elif isinstance(exception, app_commands.CommandOnCooldown):
        now = discord.utils.utcnow()
        seconds = float(re.search(r"(\d+\.\d{2})s", str(exception)).group(1))
        end = now + datetime.timedelta(seconds=seconds)
        embed = embeds.ErrorEmbed(
            description=(
                f"Command is on cooldown. "
                f"Cooldown ends {discord.utils.format_dt(end, style='R')}.\n"
                f"This message will be deleted at the same time."
            )
        )
        if itx.response.is_done():
            await itx.edit_original_response(
                embed=embed,
            )
        else:
            await itx.response.send_message(
                embed=embed,
                ephemeral=True,
            )
        await utils.delete_interaction(itx, minutes=seconds / 60)
    else:
        capture_exception(exception)
        content = (
            "This message will delete in "
            f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
        )
        edit = itx.edit_original_response if itx.response.is_done() else itx.response.send_message
        embed = embeds.ErrorEmbed(
            description=(
                f"{content}\n"
                "Unknown.\n"
                "It has been logged and sent to <@141372217677053952>.\n"
                "Please try again later."
            ),
            unknown=True,
        )
        await edit(
            embed=embed,
        )

        channel = itx.client.get_channel(1246119546650235014)

        command_name = f"**Command:** `{itx.command.name}`\n"
        channel_name = f"**Channel:** `{itx.channel}`\n"
        user_name = f"**User:** `{itx.user}`"
        args = [f"┣ **{k}:** `{v}`\n" for k, v in itx.namespace.__dict__.items()]
        if args:
            args[-1] = "┗" + args[-1][1:]
        args_name = "**Args:**\n" + "".join(args)
        formatted_tb = "".join(traceback.format_exception(None, exception, exception.__traceback__))
        discord_text_limit_minus_extra_text = 1850
        if len(formatted_tb) < discord_text_limit_minus_extra_text:
            await channel.send(f"{command_name}{args_name}{channel_name}{user_name}\n```py\n" + formatted_tb + "\n```")
        else:
            await channel.send(
                f"{command_name} {args_name} {channel_name} {user_name}",
                file=discord.File(
                    fp=io.BytesIO(
                        bytearray(
                            str(exception) + formatted_tb,
                            "utf-8",
                        )
                    ),
                    filename="error.log",
                ),
            )
    await utils.delete_interaction(itx, minutes=1)
