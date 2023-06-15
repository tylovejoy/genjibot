from __future__ import annotations

import asyncio
import contextlib
import operator
import re
import typing

import discord
from thefuzz import fuzz

import utils
import views

if typing.TYPE_CHECKING:
    import core


async def delete_interaction(
    itx: discord.Interaction[core.Genji], *, minutes: int | float
):
    """Delete an itx message after x minutes. Fails silently.
    Args:
        itx (discord.Interaction): Interaction to find original message.
        minutes (int): Minutes (use 0 for no delay)
    """
    if minutes < 0:
        raise ValueError("Time cannot be negative.")
    await asyncio.sleep(60 * minutes)
    with contextlib.suppress(
        discord.HTTPException, discord.NotFound, discord.Forbidden
    ):
        await itx.delete_original_response()


def fuzz_(string: str, iterable: typing.Iterable[str]) -> str:
    """Fuzz a value."""
    values = [(val, fuzz.ratio(string, val)) for val in iterable]
    return str(max(values, key=operator.itemgetter(1))[0])


def fuzz_multiple(string: str, iterable: typing.Iterable[str]) -> list[str]:
    """Fuzz a value."""
    values = [(val, fuzz.partial_ratio(string, val)) for val in iterable]
    values = sorted(values, key=operator.itemgetter(1), reverse=True)[:10]
    values = list(map(lambda x: x[0], values))
    return values


class MapCacheData(typing.TypedDict):
    user_ids: list[int]
    archived: bool


class UserCacheData(typing.TypedDict):
    nickname: str
    alertable: bool
    flags: int


_RANK_THRESHOLD = (10, 10, 10, 10, 7, 3)


async def update_affected_users(
    client: core.Genji,
    map_code: str,
):
    users = [
        x.user_id
        async for x in client.database.get(
            """
            SELECT DISTINCT user_id FROM records WHERE map_code=$1;
            """,
            map_code,
        )
    ]
    if users:
        for x in users:
            if user := client.get_guild(utils.GUILD_ID).get_member(x):
                await utils.auto_role(client, user)


async def auto_role(client: core.Genji, user: discord.Member):
    rank, rank_plus, silver, bronze = await rank_finder(client, user)
    rank_roles = list(
        map(
            lambda x: client.get_guild(utils.GUILD_ID).get_role(x),
            utils.Roles.ranks()[1:],
        )
    )
    rank_plus_roles = list(
        map(
            lambda x: client.get_guild(utils.GUILD_ID).get_role(x),
            utils.Roles.gold_plus()[1:],
        )
    )

    rank_silver_roles = list(
        map(
            lambda x: client.get_guild(utils.GUILD_ID).get_role(x),
            utils.Roles.silver_plus()[1:],
        )
    )
    rank_bronze_roles = list(
        map(
            lambda x: client.get_guild(utils.GUILD_ID).get_role(x),
            utils.Roles.bronze_plus()[1:],
        )
    )

    added = (
        list(filter(lambda x: x not in user.roles, rank_roles[:rank]))
        + list(filter(lambda x: x not in user.roles, rank_plus_roles[:rank_plus]))
        + list(filter(lambda x: x not in user.roles, rank_silver_roles[:silver]))
        + list(filter(lambda x: x not in user.roles, rank_bronze_roles[:bronze]))
    )
    removed = (
        list(filter(lambda x: x in user.roles, rank_roles[rank:]))
        + list(filter(lambda x: x in user.roles, rank_plus_roles[rank_plus:]))
        + list(filter(lambda x: x in user.roles, rank_silver_roles[silver:]))
        + list(filter(lambda x: x in user.roles, rank_bronze_roles[bronze:]))
    )
    new_roles = user.roles
    for a in added:
        if a not in new_roles:
            new_roles.append(a)
    for r in removed:
        if r in new_roles:
            new_roles.remove(r)

    if set(new_roles) != set(user.roles):
        await user.edit(roles=new_roles)

        await client.database.set(
            """UPDATE users SET rank=$2 WHERE user_id=$1;""",
            user.id,
            rank,
        )

    response = (
        "🚨***ALERT!***🚨\nYour roles have been updated! If roles have been removed, "
        "it's because a map that you have completed has changed difficulty.\n"
        "Complete more maps to get your roles back!\n"
    )
    if added:
        response += ", ".join([f"**{x.name}**" for x in added]) + " has been added.\n"
        client.dispatch("newsfeed_role", client, user, added)

    if removed:
        response += (
            ", ".join([f"**{x.name}**" for x in removed]) + " has been removed.\n"
        )

    if added or removed:
        with contextlib.suppress(discord.errors.HTTPException):
            flags = client.cache.users[user.id].flags
            if utils.SettingFlags.PROMOTION in flags:
                await user.send(response)


async def rank_finder(
    client: core.Genji, user: discord.Member
) -> tuple[int, int, int, int]:
    amounts = await get_completions_data(client, user.id)
    rank = 0
    gold_rank = 0
    silver_rank = 0
    bronze_rank = 0
    for i, diff in enumerate(utils.DIFFICULTIES[1:]):  # Ignore Beginner
        if diff not in amounts or amounts[diff][0] < _RANK_THRESHOLD[i]:
            break
        if amounts[diff][0] >= _RANK_THRESHOLD[i]:
            rank += 1
            all_ranks = sum((gold_rank, silver_rank, bronze_rank))
            if amounts[diff][1] >= _RANK_THRESHOLD[i] and all_ranks + 1 == rank:
                gold_rank += 1
            elif amounts[diff][2] >= _RANK_THRESHOLD[i] and all_ranks + 1 == rank:
                silver_rank += 1
            elif amounts[diff][3] >= _RANK_THRESHOLD[i] and all_ranks + 1 == rank:
                bronze_rank += 1
    return rank, gold_rank, silver_rank, bronze_rank


async def get_completions_data(
    client: core.Genji, user: int, include_beginner: bool = False
) -> dict[str, tuple[int, int, int, int]]:
    if include_beginner:
        clause = (
            "('[0.0,0.59)'::numrange, 'Beginner'), ('[0.59,2.35)'::numrange, 'Easy'),"
        )
    else:
        clause = "('[0.0,2.35)'::numrange, 'Easy'),"

    query = f"""
        WITH unioned_records AS (
            SELECT  map_code,
                    user_id,
                    record,
                    screenshot,
                    video,
                    verified,
                    message_id,
                    channel_id,
                    NULL AS medal
            FROM records
            UNION
            SELECT  map_code,
                    user_id,
                    record,
                    screenshot,
                    video,
                    TRUE AS verified,
                    message_id,
                    channel_id,
                    medal
                    FROM legacy_records
        ),
        ranges ("range", "name") AS (
             VALUES  {clause}
                     
                     ('[2.35,4.12)'::numrange, 'Medium'),
                     ('[4.12,5.88)'::numrange, 'Hard'),
                     ('[5.88,7.65)'::numrange, 'Very Hard'),
                     ('[7.65,9.41)'::numrange, 'Extreme'),
                     ('[9.41,10.0]'::numrange, 'Hell')
        ),
        map_data AS (
            SELECT DISTINCT ON (m.map_code, r.user_id) 
                AVG(mr.difficulty)                                            AS difficulty,
                VERIFIED = TRUE AND (record <= gold OR medal LIKE 'Gold')     AS gold,
                VERIFIED = TRUE AND
                (record <= silver AND record > gold OR medal LIKE 'silver')   AS silver,
                VERIFIED = TRUE AND
                (record <= bronze AND record > silver OR medal LIKE 'Bronze') AS bronze
            FROM unioned_records r
                LEFT JOIN maps m ON r.map_code = m.map_code
                LEFT JOIN map_ratings mr ON m.map_code = mr.map_code
                LEFT JOIN map_medals mm ON r.map_code = mm.map_code
            WHERE r.user_id = $1
                AND m.official = TRUE
                AND m.archived = FALSE
            GROUP BY m.map_code, record, gold, silver, bronze, VERIFIED, medal, r.user_id
        )
        SELECT COUNT(name)                        AS completions,
               name                               AS difficulty,
               COUNT(CASE WHEN gold THEN 1 END)   AS gold,
               COUNT(CASE WHEN silver THEN 1 END) AS silver,
               COUNT(CASE WHEN bronze THEN 1 END) AS bronze
        FROM ranges r
             INNER JOIN map_data md ON r.range @> md.difficulty
        GROUP BY name;
    """
    amounts = {
        x.difficulty: tuple(map(int, (x.completions, x.gold, x.silver, x.bronze)))
        async for x in client.database.get(query, user)
    }
    return amounts


class FakeUser:
    def __init__(self, id_: int, data: utils.UserData):
        self.id = id_
        self.nickname = data.nickname
        self.mention = data.nickname
        self.display_avatar = FakeAvatar()


class FakeAvatar:
    url: str = "https://cdn.discordapp.com/embed/avatars/2.png"


def wrap_string_with_percent(string: str):
    if not string:
        return
    return "%" + string + "%"


def split_nth_iterable(*, current: int, iterable: list[typing.Any], split: int):
    return (
        (current != 0 and current % split == 0)
        or (current == 0 and len(iterable) == 1)
        or current == len(iterable) - 1
    )
