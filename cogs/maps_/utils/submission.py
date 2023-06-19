from __future__ import annotations

import typing
from datetime import timedelta

import discord

from cogs.maps_.views.submission import MapSubmissionView
from utils import (
    MapSubmission,
    InvalidMedals,
    MaxMapsInPlaytest,
    MaxWeeklyMapsInPlaytest,
)

if typing.TYPE_CHECKING:
    import core


async def start_map_submission(
    itx: discord.Interaction[core.Genji],
    data: MapSubmission,
    is_mod: bool = False,
) -> None:
    """
    Submit your map to the database.

    Args:
        itx: Interaction
        data: MapSubmission obj
        is_mod: Mod command
    """

    await itx.response.defer(ephemeral=True)

    if data.medals:
        if not 0 < data.gold < data.silver < data.bronze:
            raise InvalidMedals

    if await _check_max_limit(itx) >= 5:
        raise MaxMapsInPlaytest
    count, date = await _check_weekly_limit(itx)
    if count >= 2:
        date = date + timedelta(weeks=1)
        raise MaxWeeklyMapsInPlaytest(
            "You will be able to submit again "
            f"{discord.utils.format_dt(date, 'R')}"
            f"| {discord.utils.format_dt(date, 'F')}"
        )

    initial_message = (
        f"{data.creator.mention}, "
        f"fill in additional details to complete map submission!"
    )
    view = MapSubmissionView(itx, initial_message, data, is_mod)
    await view.start()


async def _check_weekly_limit(itx: discord.Interaction[core.Genji]):
    query = """
        SELECT count(*), min(date) AS date
          FROM map_submission_dates
         WHERE
           user_id = $1 AND date BETWEEN now() - INTERVAL '1 weeks' AND now();
    """
    row = await itx.client.database.get_row(query, itx.user.id)
    return row.get("count", 0), row.get("date", None)


async def _check_max_limit(itx: discord.Interaction[core.Genji]):
    query = """
        SELECT count(*) FROM playtest WHERE is_author = TRUE AND user_id = $1;
    """
    row = await itx.client.database.get_row(query, itx.user.id)
    return row.get("count", 0)
