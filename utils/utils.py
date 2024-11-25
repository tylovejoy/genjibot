from __future__ import annotations

import asyncio
import contextlib
import logging
import operator
import typing

import discord
from thefuzz import fuzz

from utils import cache, constants
from utils.maps import DIFF_TO_RANK
from utils.models import RankDetail

if typing.TYPE_CHECKING:
    import core
    import database


log = logging.getLogger(__name__)


_emoji_numbers = {
    0: "0️⃣",
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
}


async def delete_interaction(itx: discord.Interaction[core.Genji], *, minutes: float) -> None:
    """Delete an itx message after x minutes. Fails silently.

    Args:
        itx (discord.Interaction): Interaction to find original message.
        minutes (int): Minutes (use 0 for no delay)

    """
    if minutes < 0:
        raise ValueError("Time cannot be negative.")
    await asyncio.sleep(60 * minutes)
    with contextlib.suppress(discord.HTTPException, discord.NotFound, discord.Forbidden):
        await itx.delete_original_response()


def fuzz_(string: str, iterable: typing.Iterable[str]) -> str:
    """Fuzz a value."""
    values = [(val, fuzz.ratio(string, val)) for val in iterable]
    return str(max(values, key=operator.itemgetter(1))[0])


def fuzz_multiple(string: str, iterable: typing.Iterable[str]) -> list[str]:
    """Fuzz a value."""
    values = [(val, fuzz.partial_ratio(string, val)) for val in iterable]
    values = sorted(values, key=operator.itemgetter(1), reverse=True)[:10]
    values = [x[0] for x in values]
    return values


class MapCacheData(typing.TypedDict):
    user_ids: list[int]
    archived: bool


class UserCacheData(typing.TypedDict):
    nickname: str
    alertable: bool
    flags: int


_RANK_THRESHOLD = (10, 10, 10, 10, 7, 3)


async def fetch_user_rank_data(
    db: database.Database, user_id: int, include_archived: bool, include_beginner: bool
) -> list[RankDetail]:
    """Fetch user rank data."""
    query = """
        WITH unioned_records AS (
            (
                SELECT DISTINCT ON (map_code, user_id)
                    map_code,
                    user_id,
                    record,
                    screenshot,
                    video,
                    verified,
                    message_id,
                    channel_id,
                    completion,
                    NULL AS medal
                FROM records
                ORDER BY map_code, user_id, inserted_at DESC
            )
            UNION ALL
            (
                SELECT DISTINCT ON (map_code, user_id)
                    map_code,
                    user_id,
                    record,
                    screenshot,
                    video,
                    TRUE AS verified,
                    message_id,
                    channel_id,
                    FALSE AS completion,
                    medal
                FROM legacy_records
                ORDER BY map_code, user_id, inserted_at DESC
            )
        ),
        ranges AS (
            SELECT range, name FROM
            (
                VALUES
                    ('[0.0,0.59)'::numrange, 'Beginner', TRUE),
                    ('[0.59,2.35)'::numrange, 'Easy', TRUE),
                    ('[0.0,2.35)'::numrange, 'Easy', FALSE),
                    ('[2.35,4.12)'::numrange, 'Medium', NULL),
                    ('[4.12,5.88)'::numrange, 'Hard', NULL),
                    ('[5.88,7.65)'::numrange, 'Very Hard', NULL),
                    ('[7.65,9.41)'::numrange, 'Extreme', NULL),
                    ('[9.41,10.0]'::numrange, 'Hell', NULL)
            ) AS ranges("range", "name", "includes_beginner")
            WHERE includes_beginner = $3 OR includes_beginner IS NULL
            --($3 IS TRUE OR (includes_beginner = TRUE AND includes_beginner IS NULL))
            -- includes_beginner = $3 OR includes_beginner IS NULL
        ),
        thresholds AS (
            -- Mapping difficulty names to thresholds using VALUES
            SELECT * FROM (
                VALUES
                    ('Easy', 10),
                    ('Medium', 10),
                    ('Hard', 10),
                    ('Very Hard', 10),
                    ('Extreme', 7),
                    ('Hell', 3)
            ) AS t(name, threshold)
        ),
        map_data AS (
            SELECT DISTINCT ON (m.map_code, r.user_id)
                AVG(mr.difficulty) AS difficulty,
                r.verified = TRUE AND r.video IS NOT NULL AND(
                    record <= gold OR medal LIKE 'Gold'
                    ) AS gold,
                r.verified = TRUE AND r.video IS NOT NULL AND(
                    record <= silver AND record > gold OR medal LIKE 'Silver'
                    ) AS silver,
                r.verified = TRUE AND r.video IS NOT NULL AND(
                    record <= bronze AND record > silver OR medal LIKE 'Bronze'
                ) AS bronze
            FROM unioned_records r
            LEFT JOIN maps m ON r.map_code = m.map_code
            LEFT JOIN map_ratings mr ON m.map_code = mr.map_code
            LEFT JOIN map_medals mm ON r.map_code = mm.map_code
            WHERE r.user_id = $1
              AND m.official = TRUE
              AND ($2 IS TRUE OR m.archived = FALSE)
            GROUP BY m.map_code, record, gold, silver, bronze, r.verified, medal, r.user_id
        ), counts_data AS (
        SELECT
            r.name AS difficulty,
            count(r.name) AS completions,
            count(CASE WHEN gold THEN 1 END) AS gold,
            count(CASE WHEN silver THEN 1 END) AS silver,
            count(CASE WHEN bronze THEN 1 END) AS bronze,
            -- Use threshold for rank comparison
            count(r.name) >= t.threshold AS rank_met,
            count(CASE WHEN gold THEN 1 END) >= t.threshold AS gold_rank_met,
            count(CASE WHEN silver THEN 1 END) >= t.threshold AS silver_rank_met,
            count(CASE WHEN bronze THEN 1 END) >= t.threshold AS bronze_rank_met
        FROM ranges r
        INNER JOIN map_data md ON r.range @> md.difficulty
        INNER JOIN thresholds t ON r.name = t.name
        GROUP BY r.name, t.threshold
        )
        SELECT
            name AS difficulty,
            coalesce(completions, 0) AS completions,
            coalesce(gold, 0) AS gold,
            coalesce(silver, 0) AS silver,
            coalesce(bronze, 0) AS bronze,
            coalesce(rank_met, FALSE) AS rank_met,
            coalesce(gold_rank_met, FALSE) AS gold_rank_met,
            coalesce(silver_rank_met, FALSE) AS silver_rank_met,
            coalesce(bronze_rank_met, FALSE) AS bronze_rank_met
        FROM thresholds t
        LEFT JOIN counts_data cd ON t.name = cd.difficulty
        ORDER BY
        CASE name
            WHEN 'Easy' THEN 1
            WHEN 'Medium' THEN 2
            WHEN 'Hard' THEN 3
            WHEN 'Very Hard' THEN 4
            WHEN 'Extreme' THEN 5
            WHEN 'Hell' THEN 6
        END;
    """
    rows = await db.fetch(query, user_id, include_archived, include_beginner)
    return [RankDetail(**row) for row in rows]


def determine_skill_rank_roles_to_give(
    data: list[RankDetail],
    guild: discord.Guild,
) -> tuple[list[discord.Role], list[discord.Role]]:
    """Determine skill rank roles to give to a member."""
    roles_to_grant = []
    roles_to_remove = []

    for row in data:
        base_rank_name = DIFF_TO_RANK[row.difficulty]
        base_rank = discord.utils.get(guild.roles, name=base_rank_name)

        bronze = discord.utils.get(guild.roles, name=f"{base_rank_name} +")
        silver = discord.utils.get(guild.roles, name=f"{base_rank_name} ++")
        gold = discord.utils.get(guild.roles, name=f"{base_rank_name} +++")

        # Base rank
        if row.rank_met:
            roles_to_grant.append(base_rank)
        else:
            roles_to_remove.append(base_rank)

        # Rank medals
        if row.gold_rank_met:
            roles_to_grant.append(gold)
            roles_to_remove.extend([silver, bronze])
        elif row.silver_rank_met:
            roles_to_grant.append(silver)
            roles_to_remove.extend([gold, bronze])
        elif row.bronze_rank_met:
            roles_to_grant.append(bronze)
            roles_to_remove.extend([gold, silver])
        else:
            roles_to_remove.extend([gold, silver, bronze])

    return roles_to_grant, roles_to_remove


async def grant_skill_rank_roles(
    user: discord.Member,
    roles_to_grant: list[discord.Role],
    roles_to_remove: list[discord.Role],
    bot: core.Genji,
) -> None:
    """Grant skill rank roles to a Discord server Member."""
    new_roles = user.roles
    _new_roles_announce = []
    for a in roles_to_grant:
        if a not in new_roles:
            new_roles.append(a)
            _new_roles_announce.append(a)
    for r in roles_to_remove:
        if r in new_roles:
            new_roles.remove(r)

    if set(new_roles) == set(user.roles):
        return

    await user.edit(roles=new_roles)

    response = (
        "🚨***ALERT!***🚨\nYour roles have been updated! If roles have been removed, "
        "it's because a map that you have completed has changed difficulty.\n"
        "Complete more maps to get your roles back!\n"
    )
    if roles_to_grant:
        response += ", ".join([f"**{x.name}**" for x in roles_to_grant]) + " has been added.\n"
        if _new_roles_announce:
            bot.dispatch("newsfeed_role", bot, user, _new_roles_announce)

    if roles_to_remove:
        response += ", ".join([f"**{x.name}**" for x in roles_to_remove]) + " has been removed.\n"

    if roles_to_grant or roles_to_remove:
        with contextlib.suppress(discord.errors.HTTPException):
            flags = cache.SettingFlags(await bot.database.fetch_user_flags(user.id))
            if cache.SettingFlags.PROMOTION in flags:
                await user.send(response)


async def auto_skill_role(bot: core.Genji, guild: discord.Guild, user: discord.Member) -> None:
    """Perform automatic skill roles process."""
    data = await fetch_user_rank_data(bot.database, user.id, True, False)
    add, remove = determine_skill_rank_roles_to_give(data, guild)
    await grant_skill_rank_roles(user, add, remove, bot)


async def update_affected_users(client: core.Genji, guild: discord.Guild, map_code: str) -> None:
    """Update roles for users affected by map edits or changes."""
    query = "SELECT DISTINCT user_id FROM records WHERE map_code=$1;"
    rows = await client.database.fetch(query, map_code)
    ids = [row["user_id"] for row in rows]

    if ids:
        for _id in ids:
            if _user := client.get_guild(constants.GUILD_ID).get_member(_id):
                await auto_skill_role(client, guild, _user)


def find_highest_rank(data: list[RankDetail]) -> str:
    """Find the highest rank a user has."""
    highest = "Ninja"
    for row in data:
        if row.rank_met:
            highest = DIFF_TO_RANK[row.difficulty]
    return highest


class FakeUser:
    def __init__(self, id_: int, data: cache.UserData) -> None:
        self.id = id_
        self.nickname = data.nickname
        self.mention = data.nickname
        self.display_avatar = FakeAvatar()


class FakeAvatar:
    url: str = "https://cdn.discordapp.com/embed/avatars/2.png"


def wrap_string_with_percent(string: str) -> str | None:
    """Wrap a string with percent characters for use in LIKE/ILIKE SQL queries.."""
    if not string:
        return
    return "%" + string + "%"


def split_nth_iterable(*, current: int, iterable: list[typing.Any], split: int) -> bool:
    """Determine if the current iteration should be split at the nth (split) position."""
    return (
        (current != 0 and current % split == 0) or (current == 0 and len(iterable) == 1) or current == len(iterable) - 1
    )


def convert_to_emoji_number(number: int) -> str:
    """Convert a integer to the emoji version of that number."""
    # Check if the number is within the range 0-9
    if number in _emoji_numbers:
        return _emoji_numbers[number]

    # Convert the number to a string and iterate through each digit
    emoji_number = ""
    for digit in str(number):
        if digit.isdigit():
            emoji_number += _emoji_numbers[int(digit)]
        else:
            emoji_number += digit

    return emoji_number
