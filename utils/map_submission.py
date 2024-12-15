from __future__ import annotations

import datetime
import functools
from datetime import timedelta
from typing import TYPE_CHECKING

import discord

import views
from utils import constants, embeds, errors, maps
from utils.newsfeed import NewsfeedEvent

if TYPE_CHECKING:
    import core
    from database import Database


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
    assert data.gold and data.silver and data.bronze
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
    view = await views.ConfirmMapSubmission.async_build(
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
    nickname = await itx.client.database.fetch_nickname(data.creator.id)
    embed.set_author(
        name=nickname,
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


async def is_creator_of_map(db: Database, map_code: str, user_id: int) -> bool:
    """Check if a user_id is a creator of a particular map."""
    query = "SELECT EXISTS(SELECT 1 FROM map_creators WHERE map_code = $1 AND user_id = $2)"
    return await db.fetchval(query, map_code, user_id)


async def add_creator_(
    creator: int,
    itx: discord.Interaction[core.Genji],
    map_code: str,
) -> None:
    """Add creator data."""
    await itx.response.defer(ephemeral=True)
    if await is_creator_of_map(itx.client.database, map_code, creator):
        raise errors.CreatorAlreadyExistsError
    await itx.client.database.execute(
        "INSERT INTO map_creators (map_code, user_id) VALUES ($1, $2)",
        map_code,
        creator,
    )
    nickname = await itx.client.database.fetch_nickname(creator)
    await itx.edit_original_response(
        content=(f"Adding **{nickname}** " f"to list of creators for map code **{map_code}**.")
    )


async def remove_creator_(
    creator: int,
    itx: discord.Interaction[core.Genji],
    map_code: str,
    checks: bool = False,
) -> None:
    """Remove creator data."""
    await itx.response.defer(ephemeral=True)
    if not await is_creator_of_map(itx.client.database, map_code, creator):
        raise errors.CreatorDoesntExistError
    await itx.client.database.execute(
        "DELETE FROM map_creators WHERE map_code = $1 AND user_id = $2;",
        map_code,
        creator,
    )
    nickname = await itx.client.database.fetch_nickname(creator)
    await itx.edit_original_response(
        content=(f"Removing **{nickname}** " f"from list of creators for map code **{map_code}**.")
    )
