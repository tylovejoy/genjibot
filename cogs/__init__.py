from __future__ import annotations

import datetime
import functools
import pkgutil
import typing
from datetime import timedelta

import discord
from discord import app_commands

from utils.newsfeed import NewsfeedEvent
import views
from utils import cache, constants, embeds, errors, maps

if typing.TYPE_CHECKING:
    import core

EXTENSIONS = [module.name for module in pkgutil.iter_modules(__path__, f"{__package__}.")]


def case_ignore_compare(string1: str | None, string2: str | None) -> bool:
    """Compare two strings, case-insensitive.

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


async def submit_map_(
    itx: discord.Interaction[core.Genji],
    data: maps.MapSubmission,
    mod: bool = False,
) -> None:
    """Submit your map to the database.

    Args:
        itx: Interaction
        data: MapSubmission obj
        mod: Mod command

    """
    await itx.response.defer(ephemeral=True)

    if data.medals and not 0 < data.gold < data.silver < data.bronze:
        raise errors.InvalidMedalsError

    max_maps = 5
    weekly_limit = 2

    if await _check_max_limit(itx) >= max_maps:
        raise errors.MaxMapsInPlaytestError()
    count, date = await _check_weekly_limit(itx)
    if count >= weekly_limit:
        date = date + timedelta(weeks=1)
        raise errors.MaxWeeklyMapsInPlaytestError(
            "You will be able to submit again "
            f"{discord.utils.format_dt(date, 'R')}"
            f"| {discord.utils.format_dt(date, 'F')}"
        )

    initial_message = f"{data.creator.mention}, " f"fill in additional details to complete map submission!"
    view = views.ConfirmMapSubmission(
        itx,
        partial_callback=None,
        initial_message=initial_message,
    )
    callback = functools.partial(map_submission_first_step, data, itx, mod, view)
    view.partial_callback = callback
    await view.start()


async def _check_weekly_limit(
    itx: discord.Interaction[core.Genji],
) -> tuple[int, datetime.datetime | None]:
    query = """
        SELECT count(*), min(date) as date
          FROM map_submission_dates
         WHERE
           user_id = $1 AND date BETWEEN now() - INTERVAL '1 weeks' AND now();
    """
    row = await itx.client.database.fetchrow(query, itx.user.id)
    if not row:
        return 0, None
    return row.get("count", 0), row.get("date", None)


async def _check_max_limit(itx: discord.Interaction[core.Genji]) -> int:
    query = """
        SELECT count(*) FROM playtest WHERE is_author = TRUE AND user_id = $1;
    """
    row = await itx.client.database.fetchrow(query, itx.user.id)
    if not row:
        return 0
    return row.get("count", 0)


async def map_submission_first_step(
    data: maps.MapSubmission,
    itx: discord.Interaction[core.Genji],
    mod: bool,
    view: views.ConfirmMapSubmission,
) -> None:
    """Start map submission process."""
    data.set_extras(
        map_types=view.map_type.values,
        mechanics=view.mechanics.values,
        restrictions=view.restrictions.values,
        difficulty=view.difficulty.values[0],
    )
    embed = embeds.GenjiEmbed(
        title="Map Submission",
        description=str(data),
    )
    embed.set_author(
        name=itx.client.cache.users[data.creator.id].nickname,
        icon_url=data.creator.display_avatar.url,
    )
    embed = embeds.set_embed_thumbnail_maps(data.map_name, embed)
    view_final_confirmation = views.ConfirmBaseView(
        view.itx,
        partial_callback=None,
        initial_message=f"{itx.user.mention}, is this correct?",
    )
    callback = functools.partial(map_submission_second_step, data, embed, itx, mod)
    view_final_confirmation.partial_callback = callback
    await view_final_confirmation.start(embed=embed)


async def map_submission_second_step(
    data: maps.MapSubmission,
    embed: discord.Embed,
    itx: discord.Interaction[core.Genji],
    mod: bool,
) -> None:
    """Create playtest thread."""
    if not mod:
        embed.title = "Calling all Playtesters!"
        view = views.PlaytestVoting(
            data,
            itx.client,
        )
        playtest_message = await itx.guild.get_channel(constants.PLAYTEST).send(
            content=f"Total Votes: 0 / {view.required_votes}", embed=embed
        )
        embed = embeds.GenjiEmbed(
            title="Difficulty Ratings",
            description="You can change your vote, but you cannot cast multiple!\n\n",
        )
        thread = await playtest_message.create_thread(
            name=(f"{data.map_code} | {data.difficulty} | {data.map_name} " f"{data.checkpoint_count} CPs")
        )

        thread_msg = await thread.send(
            "Discuss, play, rate, etc.",
            view=view,
            embed=embed,
        )
        itx.client.playtest_views[thread_msg.id] = view
        await thread.send(
            f"{itx.user.mention}, you can receive feedback on your map here. "
            f"I'm pinging you so you are able to join this thread automatically!"
        )

        await data.insert_playtest(itx, thread.id, thread_msg.id, playtest_message.id)
    await data.insert_all(itx, mod)
    itx.client.cache.maps.add_one(
        cache.MapData(
            map_code=data.map_code,
            user_ids=[data.creator.id],
            archived=False,
        )
    )
    if not mod:
        map_maker = itx.guild.get_role(constants.Roles.MAP_MAKER)
        if map_maker not in itx.user.roles:
            await itx.user.add_roles(map_maker, reason="Submitted a map.")
    else:
        nickname = await itx.client.database.fetch_nickname(data.creator.id)
        _data = {
            "user": {
                "user_id": data.creator.id,
                "nickname": nickname,
            },
            "map": {
                "map_code": data.map_code,
                "difficulty": data.difficulty,
                "map_name": data.map_name,
            },
        }
        event = NewsfeedEvent("new_map", _data)
        await itx.client.genji_dispatch.handle_event(event, itx.client)

    if not itx.client.cache.users.find(data.creator.id).is_creator:
        itx.client.cache.users.find(data.creator.id).update_is_creator(True)


async def add_creator_(
    creator: int,
    itx: discord.Interaction[core.Genji],
    map_code: str,
) -> None:
    """Add creator data."""
    await itx.response.defer(ephemeral=True)
    if creator in itx.client.cache.maps[map_code].user_ids:
        raise errors.CreatorAlreadyExistsError
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


async def remove_creator_(
    creator: int,
    itx: discord.Interaction[core.Genji],
    map_code: str,
    checks: bool = False,
) -> None:
    """Remove creator data."""
    await itx.response.defer(ephemeral=True)
    if creator not in itx.client.cache.maps[map_code].user_ids:
        raise errors.CreatorDoesntExistError
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
