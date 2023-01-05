from __future__ import annotations

import typing

from discord import app_commands

import utils

if typing.TYPE_CHECKING:
    import core


class MapNameTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_names:
            value = utils.fuzz_(value, itx.client.map_names)
        return value


class MapTypeTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_types:
            value = utils.fuzz_(value, itx.client.map_types)
        return value


class MapMechanicsTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_techs:
            value = utils.fuzz_(value, itx.client.map_techs)
        return value


class MapRestrictionsTransformer(app_commands.Transformer):
    async def transform(self, itx: core.Interaction[core.Genji], value: str) -> str:
        if value not in itx.client.map_restrictions:
            value = utils.fuzz_(value, itx.client.map_restrictions)
        return value
