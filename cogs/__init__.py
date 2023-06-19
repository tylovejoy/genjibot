from __future__ import annotations

import copy
import functools
import pkgutil
import typing
from datetime import timedelta

import discord
from discord import app_commands

import utils
import views
from utils import MaxMapsInPlaytest, MaxWeeklyMapsInPlaytest, new_map_newsfeed

if typing.TYPE_CHECKING:
    import core

EXTENSIONS = [
    module.name for module in pkgutil.iter_modules(__path__, f"{__package__}.")
]


def case_ignore_compare(string1: str | None, string2: str | None) -> bool:
    """
    Compare two strings, case-insensitive.
    Args:
        string1 (str): String 1 to compare
        string2 (str): String 2 to compare
    Returns:
        True if string2 is in string1
    """
    if string1 is None or string2 is None:
        return False
    return string2.casefold() in string1.casefold()


async def _autocomplete(
    current: str,
    choices: list[app_commands.Choice[str]],
) -> list[app_commands.Choice[str]]:
    if not choices:  # Quietly ignore empty choices
        return []
    if current == "":
        response = choices[:25]
    else:
        response = [x for x in choices if case_ignore_compare(x.name, current)][:25]
    return response


async def creator_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.cache.users.creator_choices)


async def map_codes_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    current = current.replace("O", "0").replace("o", "0")
    return await _autocomplete(current, itx.client.cache.maps.choices)


async def map_name_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.cache.map_names.choices)


async def map_type_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.cache.map_types.choices)


async def map_mechanics_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.cache.map_mechanics.choices)


async def tags_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.cache.tags.choices)


async def users_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.cache.users.choices)


async def add_creator_(
    creator: int,
    itx: discord.Interaction[core.Genji],
    map_code: str,
):
    await itx.response.defer(ephemeral=True)
    if creator in itx.client.cache.maps[map_code].user_ids:
        raise utils.CreatorAlreadyExists
    await itx.client.database.set(
        "INSERT INTO map_creators (map_code, user_id) VALUES ($1, $2)",
        map_code,
        creator,
    )
    itx.client.cache.maps[map_code].add_creator(creator)
    itx.client.cache.users[creator].is_creator = True
    await itx.edit_original_response(
        content=(
            f"Adding **{itx.client.cache.users[creator].nickname}** "
            f"to list of creators for map code **{map_code}**."
        )
    )


async def remove_creator_(creator, itx, map_code, checks: bool = False):
    await itx.response.defer(ephemeral=True)
    if creator not in itx.client.cache.maps[map_code].user_ids:
        raise utils.CreatorDoesntExist
    await itx.client.database.set(
        "DELETE FROM map_creators WHERE map_code = $1 AND user_id = $2;",
        map_code,
        creator,
    )
    itx.client.cache.maps[map_code].remove_creator(creator)
    await itx.edit_original_response(
        content=(
            f"Removing **{itx.client.cache.users[creator].nickname}** "
            f"from list of creators for map code **{map_code}**."
        )
    )
