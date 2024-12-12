from __future__ import annotations

from typing import TYPE_CHECKING

from .utils import case_ignore_compare

if TYPE_CHECKING:
    import discord
    from discord import app_commands

    import core


async def _autocomplete(
    current: str,
    choices: list[app_commands.Choice[str]],
) -> list[app_commands.Choice[str]]:
    if not choices:  # Quietly ignore empty choices
        return []
    return choices[:25] if current == "" else [x for x in choices if case_ignore_compare(x.name, current)][:25]


async def creator_autocomplete(itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
    """Run autocompletion for creator names."""
    return await _autocomplete(current, itx.client.cache.users.creator_choices)


async def map_codes_autocomplete(itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
    """Run autocompletion for map codes."""
    current = current.replace("O", "0").replace("o", "0")
    return await _autocomplete(current, itx.client.cache.maps.choices)


async def map_name_autocomplete(itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
    """Run autocompletion for map names."""
    return await _autocomplete(current, itx.client.cache.map_names.choices)


async def map_type_autocomplete(itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
    """Run autocompletion for map types."""
    return await _autocomplete(current, itx.client.cache.map_types.choices)


async def map_mechanics_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    """Run autocompletion for map mechanics."""
    return await _autocomplete(current, itx.client.cache.map_mechanics.choices)


async def map_restrictions_autocomplete(
    itx: discord.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    """Run autocompletion for map restrictions."""
    return await _autocomplete(current, itx.client.cache.map_restrictions.choices)


async def tags_autocomplete(itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
    """Run autocompletion for tags."""
    return await _autocomplete(current, itx.client.cache.tags.choices)


async def users_autocomplete(itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
    """Run autocompletion for users."""
    return await _autocomplete(current, itx.client.cache.users.choices)
