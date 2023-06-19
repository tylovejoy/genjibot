from __future__ import annotations

import typing
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from cogs import map_name_autocomplete, users_autocomplete
from cogs.command_groups import map_commands
from cogs.maps.utils.submission import start_map_submission
from utils import (
    GUILD_ID,
    MapCodeSubmitTransformer,
    MapNameTransformer,
    RecordTransformer,
    MapSubmission,
    FakeUser,
    AllUserTransformer,
    BaseMapData,
)

if typing.TYPE_CHECKING:
    import core


class MapSubmissions(commands.Cog):
    """Map submissions"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="submot-map")
    @app_commands.guilds(
        discord.Object(id=GUILD_ID), discord.Object(id=868981788968640554)
    )
    @app_commands.autocomplete(map_name=map_name_autocomplete)
    async def submit_map(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, RecordTransformer] | None = None,
        silver: app_commands.Transform[float, RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, RecordTransformer] | None = None,
    ) -> None:
        """
        Submit your map to get playtested.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            map_name: Overwatch map
            checkpoint_count: Number of checkpoints in the map
            description: Other optional information for the map
            guide_url: Guide URL
            gold: Gold medal time (must be the fastest time)
            silver: Silver medal time (must be between gold and bronze)
            bronze: Bronze medal time (must be the slowest time)
        """
        medals = None
        if gold and silver and bronze:
            medals = (gold, silver, bronze)

        map_data = BaseMapData(
            itx.user,
            map_code,
            map_name,
            checkpoint_count,
            description,
            medals,
            guides=[guide_url],
        )

        await start_map_submission(
            itx,
            map_data,
        )

    @map_commands.command(name="submot-map")
    @app_commands.autocomplete(
        user=users_autocomplete,
        map_name=map_name_autocomplete,
    )
    async def mod_submit_map(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[FakeUser | discord.Member, AllUserTransformer],
        map_code: app_commands.Transform[str, MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, RecordTransformer] | None = None,
        silver: app_commands.Transform[float, RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, RecordTransformer] | None = None,
    ) -> None:
        """
        Submit a map for a specific user to the database This will skip the playtesting phase.

        Args:
            itx: Interaction
            user: user
            map_code: Overwatch share code
            map_name: Overwatch map
            checkpoint_count: Number of checkpoints in the map
            description: Other optional information for the map
            guide_url: Guide URL
            gold: Gold medal time (must be the fastest time)
            silver: Silver medal time (must be between gold and bronze)
            bronze: Bronze medal time (must be the slowest time)
        """

        medals = None
        if gold and silver and bronze:
            medals = (gold, silver, bronze)

        map_submission = MapSubmission(
            creator=user,
            map_code=map_code,
            map_name=map_name,
            checkpoint_count=checkpoint_count,
            description=description,
            guides=[guide_url],
            medals=medals,
        )
        await start_map_submission(
            itx,
            map_submission,
            is_mod=True,
        )
