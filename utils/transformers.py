from __future__ import annotations

import re
from typing import TYPE_CHECKING

from discord import app_commands

from . import constants, errors, utils
from .records import CODE_VERIFICATION

if TYPE_CHECKING:
    import discord

    import core


async def transform_user(client: core.Genji, value: str) -> utils.FakeUser | discord.Member:
    """Transform user."""
    guild = client.get_guild(constants.GUILD_ID)
    assert guild
    try:
        _value = int(value)
        member = guild.get_member(_value)
        if member:
            return member
        nickname = await client.database.fetch_nickname(_value)
        return utils.FakeUser(_value, nickname)
    except ValueError:
        raise errors.UserNotFoundError


class MapNameTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        query = "SELECT name FROM all_map_names ORDER BY similarity(name, $1::text) DESC LIMIT 1;"
        return await itx.client.database.fetchval(query, value)

    async def autocomplete(
        self,
        itx: discord.Interaction[core.Genji],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = "SELECT name FROM all_map_names ORDER BY similarity(name, $1::text) DESC LIMIT 10;"
        names = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=x, value=x) for (x,) in names]


class MapTypesTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        query = "SELECT name FROM all_map_types ORDER BY similarity(name, $1::text) DESC LIMIT 1;"
        return await itx.client.database.fetchval(query, value)

    async def autocomplete(
        self,
        itx: discord.Interaction[core.Genji],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = "SELECT name FROM all_map_types ORDER BY similarity(name, $1::text) DESC LIMIT 10;"
        types = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=x, value=x) for (x,) in types]


class MapMechanicsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        query = "SELECT name FROM all_map_mechanics ORDER BY similarity(name, $1::text) DESC LIMIT 1;"
        return await itx.client.database.fetchval(query, value)

    async def autocomplete(
        self,
        itx: discord.Interaction[core.Genji],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = "SELECT name FROM all_map_mechanics ORDER BY similarity(name, $1::text) DESC LIMIT 10;"
        mechanics = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=x, value=x) for (x,) in mechanics]


class MapRestrictionsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        query = "SELECT name FROM all_map_restrictions ORDER BY similarity(name, $1::text) DESC LIMIT 1;"
        return await itx.client.database.fetchval(query, value)

    async def autocomplete(
        self,
        itx: discord.Interaction[core.Genji],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = "SELECT name FROM all_map_restrictions ORDER BY similarity(name, $1::text) DESC LIMIT 10;"
        restrictions = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=x, value=x) for (x,) in restrictions]


class _MapCodeBaseTransformer(app_commands.Transformer):
    @staticmethod
    def _clean_code(map_code: str) -> str:
        return map_code.upper().replace("O", "0").lstrip().rstrip()


class MapCodeSubmitTransformer(_MapCodeBaseTransformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = self._clean_code(value)
        if not re.match(CODE_VERIFICATION, value):
            raise errors.IncorrectCodeFormatError
        if await itx.client.database.is_existing_map_code(value):
            raise errors.MapExistsError
        return value


class _MapCodeAutocompleteBaseTransformer(_MapCodeBaseTransformer):
    async def autocomplete(self, itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
        query = "SELECT map_code FROM maps WHERE archived = FALSE ORDER BY similarity(map_code, $1) DESC LIMIT 5;"
        results = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=a, value=a) for (a,) in results]


class MapCodeTransformer(_MapCodeAutocompleteBaseTransformer):
    @staticmethod
    def _clean_code(map_code: str) -> str:
        return map_code.upper().replace("O", "0").lstrip().rstrip()

    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = self._clean_code(value)
        if not re.match(CODE_VERIFICATION, value):
            raise errors.IncorrectCodeFormatError
        query = "SELECT map_code FROM maps WHERE archived = FALSE ORDER BY similarity(map_code, $1) DESC LIMIT 1;"
        res = await itx.client.database.fetch(query, value)
        if not res or res[0]["map_code"] != value:
            raise errors.NoMapsFoundError
        return value


class MapCodeRecordsTransformer(_MapCodeAutocompleteBaseTransformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = self._clean_code(value)

        if not await itx.client.database.is_existing_map_code(value):
            raise errors.InvalidMapCodeError

        if not re.match(CODE_VERIFICATION, value):
            raise errors.IncorrectCodeFormatError

        return value


class CreatorTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> int:
        user = await transform_user(itx.client, value)
        if not user:
            raise errors.UserNotFoundError
        else:
            return user.id

    async def autocomplete(self, itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
        query = """
            WITH creators AS (
              SELECT u.user_id, nickname FROM users u
              RIGHT JOIN map_creators mc ON u.user_id = mc.user_id
            )
            SELECT DISTINCT nickname, user_id, similarity(nickname, $1::text)
            FROM creators ORDER BY similarity(nickname, $1::text) DESC LIMIT 6;
        """
        results = await itx.client.database.fetch(query, current)
        return [
            app_commands.Choice(name=f"{row['nickname']} ({row['user_id']})", value=str(row["user_id"]))
            for row in results
        ]


class AllUserTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> utils.FakeUser | discord.Member:
        return await transform_user(itx.client, value)

    async def autocomplete(self, itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
        query = "SELECT user_id, nickname FROM USERS ORDER BY similarity(nickname, $1) DESC LIMIT 10;"
        results = await itx.client.database.fetch(query, current)
        return [
            app_commands.Choice(name=f"{row['nickname']} ({row['user_id']})", value=str(row["user_id"]))
            for row in results
        ]


class FakeUserTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> utils.FakeUser | discord.Member:
        user = await transform_user(itx.client, value)
        if isinstance(user, utils.FakeUser):
            return user
        raise errors.FakeUserNotFoundError

    async def autocomplete(self, itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
        query = """
            SELECT user_id, nickname
            FROM USERS
            WHERE user_id < 10000000
            ORDER BY similarity(nickname, $1) DESC
            LIMIT 10;
        """
        results = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=f"{nick} ({id_})", value=nick) for id_, nick in results]


class RecordTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> float:
        try:
            return time_convert(value)
        except ValueError:
            raise errors.IncorrectRecordFormatError


class URLTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = value.strip()
        if not value.startswith("https://") and not value.startswith("http://"):
            value = "https://" + value
        try:
            async with itx.client.session.get(value) as resp:
                if resp.status != 200:  # noqa: PLR2004
                    raise errors.IncorrectURLFormatError
                return str(resp.url)
        except Exception:
            raise errors.IncorrectURLFormatError


def time_convert(string: str) -> float:
    """Convert HH:MM:SS.ss string into seconds (float)."""
    negative = -1 if string[0] == "-" else 1
    time = string.split(":")
    match len(time):
        case 1:
            res = float(time[0])
        case 2:
            res = float((int(time[0]) * 60) + (negative * float(time[1])))
        case 3:
            res = float((int(time[0]) * 3600) + (negative * (int(time[1]) * 60)) + (negative * float(time[2])))
        case _:
            raise ValueError("Failed to match any cases.")
    return round(res, 2)


class KeyTypeTransformer(app_commands.Transformer):
    """Transform key type."""

    async def autocomplete(self, itx: discord.Interaction[core.Genji], current: str) -> list[app_commands.Choice[str]]:
        query = "SELECT name FROM lootbox_key_types ORDER BY similarity(name, $1) DESC LIMIT 5;"
        results = await itx.client.database.fetch(query, current)
        return [app_commands.Choice(name=a, value=a) for (a,) in results]

    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        query = "SELECT name FROM lootbox_key_types ORDER BY similarity(name, $1) DESC LIMIT 1;"
        res = await itx.client.database.fetch(query, value)
        if not res or res[0]["name"] != value:
            raise errors.NoMapsFoundError
        return value
