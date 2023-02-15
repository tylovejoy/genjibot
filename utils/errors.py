from __future__ import annotations

import datetime
import io
import re
import traceback
import typing

import discord
from discord import app_commands

import utils

if typing.TYPE_CHECKING:
    from core import Genji, Interaction


class BaseParkourException(Exception):
    def __init__(self):
        super().__init__(self.__doc__)


class DatabaseConnectionError(Exception):
    """Connection failed. This will be logged. Try again later."""


class IncorrectRecordFormatError(
    BaseParkourException, app_commands.errors.AppCommandError
):
    """Record must be in XXXX.xx format e.g. 1569.33, 567.01, 10.50, etc."""


class IncorrectCodeFormatError(
    BaseParkourException, app_commands.errors.AppCommandError
):
    """Map code must be a valid Overwatch share code."""


class IncorrectURLFormatError(
    BaseParkourException, app_commands.errors.AppCommandError
):
    """The given URL is invalid."""


class InvalidFiltersError(BaseParkourException):
    """
    You must choose _at least_ **one** filter
    (map name, map type, or creator, mechanics, official, difficulty)
    """


class InvalidMapNameError(BaseParkourException, app_commands.errors.AppCommandError):
    """Invalid map name given. Please make sure to use the autocompleted map names."""


class InvalidMapCodeError(BaseParkourException, app_commands.errors.AppCommandError):
    """Invalid map code given. Please make sure to use the autocompleted map codes."""


class InvalidMapLevelError(BaseParkourException, app_commands.errors.AppCommandError):
    """Invalid map level given. Please make sure to use the autocompleted map levels."""


class InvalidMapTypeError(BaseParkourException, app_commands.errors.AppCommandError):
    """Invalid map name given. Please make sure to use the autocompleted map types."""


class RecordNotFasterError(BaseParkourException, app_commands.errors.AppCommandError):
    """Record must be faster than your previous submission."""


class NoMapsFoundError(BaseParkourException, app_commands.errors.AppCommandError):
    """No maps have been found with the given filters."""


class NoRecordsFoundError(BaseParkourException, app_commands.errors.AppCommandError):
    """No records have been found."""


class NoPermissionsError(BaseParkourException, app_commands.errors.AppCommandError):
    """You do not have permission to do this action."""


class CreatorAlreadyExists(BaseParkourException, app_commands.errors.AppCommandError):
    """Creator already associated with this map."""


class CreatorDoesntExist(BaseParkourException, app_commands.errors.AppCommandError):
    """Creator is not associated with this map."""


class MapExistsError(BaseParkourException, app_commands.errors.AppCommandError):
    """This map code already exists!"""


class NoGuidesExistError(BaseParkourException, app_commands.errors.AppCommandError):
    """No guides exist for this map code."""


class GuideExistsError(BaseParkourException, app_commands.errors.AppCommandError):
    """This guide has already been submitted."""


class OutOfRangeError(BaseParkourException, app_commands.errors.AppCommandError):
    """Choice is out of range."""


class InvalidInteger(BaseParkourException, app_commands.errors.AppCommandError):
    """Choice must be a valid integer."""


class UserNotFoundError(BaseParkourException, app_commands.errors.AppCommandError):
    """User does not exist."""


class RankTooLowError(BaseParkourException, app_commands.errors.AppCommandError):
    """Your rank is too low to do this action."""


class VideoNoRecord(BaseParkourException, app_commands.errors.AppCommandError):
    """If you add a video, you must submit a time record as well. Please submit again with the `record` argument."""


class InvalidFakeUser(BaseParkourException, app_commands.errors.AppCommandError):
    """This fake user does not exist."""


class InvalidMedals(BaseParkourException, app_commands.errors.AppCommandError):
    """
    Medals are incorrectly formatted.
    Make sure gold is faster than silver and silver is faster than bronze
    """


class ArchivedMap(BaseParkourException, app_commands.errors.AppCommandError):
    """Map has been archived. Records cannot be submitted."""


class CannotVerifyOwnRecords(BaseParkourException, app_commands.errors.AppCommandError):
    """You cannot verify your own records/submissions."""


class WrongCompletionChannel(BaseParkourException, app_commands.errors.AppCommandError):
    """You can only submit in <#1072898844339224627>"""


async def on_app_command_error(
    itx: Interaction[Genji], error: app_commands.errors.CommandInvokeError | Exception
):
    exception = getattr(error, "original", error)
    if isinstance(exception, utils.BaseParkourException):
        embed = utils.ErrorEmbed(description=str(exception))
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
        embed = utils.ErrorEmbed(
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
        content = (
            "This message will delete in "
            f"{discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(minutes=1), 'R')}"
        )
        edit = (
            itx.edit_original_response
            if itx.response.is_done()
            else itx.response.send_message
        )
        embed = utils.ErrorEmbed(
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

        channel = itx.client.get_channel(991795696707584062)

        command_name = f"**Command:** `{itx.command.name}`\n"
        channel_name = f"**Channel:** `{itx.channel}`\n"
        user_name = f"**User:** `{itx.user}`"
        args = [f"┣ **{k}:** `{v}`\n" for k, v in itx.namespace.__dict__.items()]
        if args:
            args[-1] = "┗" + args[-1][1:]
        args_name = "**Args:**\n" + "".join(args)
        formatted_tb = "".join(
            traceback.format_exception(None, exception, exception.__traceback__)
        )

        if len(formatted_tb) < 1850:
            await channel.send(
                f"{command_name}{args_name}{channel_name}{user_name}\n```py\n"
                + formatted_tb
                + "\n```"
            )
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
