from __future__ import annotations

import typing

import discord
from discord import app_commands

import utils

if typing.TYPE_CHECKING:
    import core


class MapNameTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_names:
            value = utils.fuzz_(value, itx.client.cache.map_names)
        return value


class MapTypeTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_types:
            value = utils.fuzz_(value, itx.client.cache.map_types)
        return value


class MapMechanicsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_mechanics:
            value = utils.fuzz_(value, itx.client.cache.map_mechanics)
        return value


class MapRestrictionsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.cache.map_restrictions:
            value = utils.fuzz_(value, itx.client.cache.map_restrictions)
        return value
