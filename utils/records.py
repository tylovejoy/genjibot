from __future__ import annotations

import datetime
import re
import typing

import discord
from discord import Embed, app_commands

from . import constants, embeds, errors, ranks, utils

if typing.TYPE_CHECKING:
    import decimal

    import asyncpg

    import core
    import database


CODE_VERIFICATION = re.compile(r"^[A-Z0-9]{4,6}$")


class MapCodeTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = value.upper().replace("O", "0").lstrip().rstrip()
        if not re.match(CODE_VERIFICATION, value):
            raise errors.IncorrectCodeFormatError
        return value


class MapCodeSubmitTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = value.upper().replace("O", "0").lstrip().rstrip()
        if not re.match(CODE_VERIFICATION, value):
            raise errors.IncorrectCodeFormatError
        if value in itx.client.cache.maps.keys:
            raise errors.MapExistsError
        return value


class MapCodeRecordsTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> str:
        value = value.upper().replace("O", "0").lstrip().rstrip()

        if value not in itx.client.cache.maps.keys:
            raise errors.InvalidMapCodeError

        if not re.match(CODE_VERIFICATION, value):
            raise errors.IncorrectCodeFormatError

        return value


class UserTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> int:
        if value not in map(str, itx.client.cache.users.keys):
            raise errors.UserNotFoundError
        return int(value)


class CreatorTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> int:
        user = await transform_user(itx.client, value)
        if not user or user.id not in itx.client.cache.users.creator_ids:
            raise errors.UserNotFoundError
        else:
            return user.id


class AllUserTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> utils.FakeUser | discord.Member:
        return await transform_user(itx.client, value)


async def transform_user(client: core.Genji, value: str) -> utils.FakeUser | discord.Member:
    """Transform user."""
    guild = client.get_guild(constants.GUILD_ID)
    try:
        value = int(value)
        member = guild.get_member(value)
        if member:
            return member
        return utils.FakeUser(value, client.cache.users[value])
    except ValueError:
        member = discord.utils.find(lambda u: utils.case_ignore_compare(u.name, value), guild.members)
        if member:
            return member
        for user in client.cache.users:
            if utils.case_ignore_compare(value, user.nickname):
                return utils.FakeUser(user.user_id, client.cache.users[user.user_id])


class RecordTransformer(app_commands.Transformer):
    async def transform(self, itx: discord.Interaction[core.Genji], value: str) -> float:
        try:
            value = time_convert(value)
        except ValueError:
            raise errors.IncorrectRecordFormatError
        return value


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


def pretty_record(record: decimal.Decimal | float) -> str:
    """Convert Decimal | float to a time formatted string.

    The pretty_record property takes the record time for a given
    document and returns a string representation of that time.
    The function is used to display the record times in an easily
    readable format on the leaderboard page.

    """
    record = float(round(record, 2))
    negative = "-" if record < 0 else ""
    dt = datetime.datetime.min + datetime.timedelta(seconds=abs(record))
    hour_remove = 0
    seconds_remove = -4

    if dt.hour == 0 and dt.minute == 0:
        hour_remove = 6
        if dt.second < 10:  # noqa: PLR2004
            hour_remove += 1

    elif dt.hour == 0:
        hour_remove = 3
        if dt.minute < 10:  # noqa: PLR2004
            hour_remove = 4

    if dt.microsecond == 0:
        seconds_remove = -4

    return negative + dt.strftime("%H:%M:%S.%f")[hour_remove:seconds_remove]


def icon_generator(record: asyncpg.Record, medals: tuple[float, float, float]) -> str:
    """Generate icon for embed."""
    icon = ""
    if record["video"] and record["record"] != "Completion":
        if record["record"] < medals[0] != 0:
            icon = constants.GOLD_WR if record.get("rank_num", 0) == 1 else constants.FULLY_VERIFIED_GOLD
        elif record["record"] < medals[1] != 0:
            icon = constants.SILVER_WR if record.get("rank_num", 0) == 1 else constants.FULLY_VERIFIED_SILVER
        elif record["record"] < medals[2] != 0:
            icon = constants.BRONZE_WR if record.get("rank_num", 0) == 1 else constants.FULLY_VERIFIED_BRONZE
        elif record.get("rank_num", 0) == 1:
            icon = constants.NON_MEDAL_WR
        else:
            icon = constants.FULLY_VERIFIED
    elif record["record"] != "Completion":
        icon = constants.PARTIAL_VERIFIED
    return icon


def all_levels_records_embed(
    records: list[database.DotRecord],
    title: str,
    legacy: bool = False,
) -> list[Embed | embeds.GenjiEmbed]:
    """Generate embed for All Levels Record."""
    embed_list = []
    embed = embeds.GenjiEmbed(title=title)
    for i, record in enumerate(records):
        if float(record.record) == constants.COMPLETION_PLACEHOLDER:
            record.record = "Completion"
        if legacy:
            medals = (
                9999999 if record.medal == "Gold" else -9999999,
                9999999 if record.medal == "Silver" else -9999999,
                9999999 if record.medal == "Bronze" else -9999999,
            )
        elif record.gold:
            medals = (record.gold, record.silver, record.bronze)
            medals = tuple(map(float, medals))
        else:
            medals = (0, 0, 0)
        if not record.video:
            description = (
                f"┣ `Name` {discord.utils.escape_markdown(record.nickname)}\n"
                f"┗ `Record` [{record.record}]"
                f"({record.screenshot}) "
                f"{icon_generator(record, medals)}\n"
            )
        else:
            description = (
                f"┣ `Name` {discord.utils.escape_markdown(record.nickname)}\n"
                f"┣ `Record` [{record.record}]"
                f"({record.screenshot}) "
                f"{icon_generator(record, medals)}\n "
                f"┗ `Video` [Link]({record.video})\n"
            )
        embed.add_field(
            name=f"{constants.PLACEMENTS.get(i + 1, '')} {make_ordinal(i + 1)}",
            # if single
            # else record.level_name,
            value=description,
            inline=False,
        )
        if utils.split_nth_iterable(current=i, iterable=records, split=10):
            embed = embeds.set_embed_thumbnail_maps(record.map_name, embed)
            embed_list.append(embed)
            embed = embeds.GenjiEmbed(title=title)
    return embed_list


def pr_records_embed(
    records: list[database.DotRecord],
    title: str,
) -> list[Embed | embeds.GenjiEmbed]:
    """Generate embed for PR Record."""
    embed_list = []
    _embed = embeds.GenjiEmbed(title=title)
    for i, record in enumerate(records):
        if float(record.record) == constants.COMPLETION_PLACEHOLDER:
            record.record = "Completion"
        cur_code = f"{record.map_name} by {record.creators} ({record.map_code})"
        description = ""
        if record.gold:
            medals = (record.gold, record.silver, record.bronze)
            medals = tuple(map(float, medals))
        else:
            medals = (0, 0, 0)
        if not record.video:
            description += (
                f"┣ `Difficulty` {ranks.convert_num_to_difficulty(record.difficulty)}\n"
                f"┣ `Record` [{record.record}]"
                f"({record.screenshot}) "
                f"{icon_generator(record, medals)}\n┃\n"
            )
        else:
            description += (
                f"┣ `Difficulty` {ranks.convert_num_to_difficulty(record.difficulty)}\n"
                f"┣ `Record` [{record.record}]"
                f"({record.screenshot})"
                f"{icon_generator(record, medals)}\n "
                f"┣ `Video` [Link]({record.video})\n┃\n"
            )
        _embed.add_field(
            name=f"{cur_code}",
            value="┗".join(description[:-3].rsplit("┣", 1)),
            inline=False,
        )
        if utils.split_nth_iterable(current=i, iterable=records, split=10):
            _embed.add_field(
                name="Legend",
                value=(
                    f"{constants.PARTIAL_VERIFIED} Completion\n"
                    f"{constants.FULLY_VERIFIED} Verified\n"
                    f"{constants.NON_MEDAL_WR} No Medal w/ World Record\n\n"
                    f"{constants.FULLY_VERIFIED_BRONZE} Bronze Medal\n"
                    f"{constants.BRONZE_WR} Bronze Medal w/ World Record\n\n"
                    f"{constants.FULLY_VERIFIED_SILVER} Silver Medal\n"
                    f"{constants.SILVER_WR} Silver Medal w/ World Record\n\n"
                    f"{constants.FULLY_VERIFIED_GOLD} Gold Medal\n"
                    f"{constants.GOLD_WR} Gold Medal w/ World Record\n"
                ),
            )
            embed_list.append(_embed)
            _embed = embeds.GenjiEmbed(title=title)
    return embed_list


def make_ordinal(n: int) -> str:
    """Convert an integer into its ordinal representation.

    make_ordinal(0)   => '0th'
    make_ordinal(3)   => '3rd'
    make_ordinal(122) => '122nd'
    make_ordinal(213) => '213th'
    """
    n = int(n)
    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:  # noqa: PLR2004
        suffix = "th"
    return str(n) + suffix
