from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    import core


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
