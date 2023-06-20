from __future__ import annotations

import random
import typing

import discord
from discord import app_commands
from discord.ext import commands

import database
import views
from cogs.maps.utils.utils import (
    MapNameTransformer,
    MapMechanicsTransformer,
    MapTypeTransformer,
)
from utils import split_nth_iterable, wrap_string_with_percent
from cogs.maps.utils.embed import MapEmbedData

if typing.TYPE_CHECKING:
    import core


class MapSearch(commands.Cog):
    """Maps"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="random-map")
    @app_commands.choices(
        minimum_rating=utils.ALL_STARS_CHOICES,
        difficulty=[app_commands.Choice(name=x, value=x) for x in utils.DIFFICULTIES],
    )
    @app_commands.guilds(
        discord.Object(id=utils.GUILD_ID), discord.Object(id=868981788968640554)
    )
    async def random_map(
        self,
        itx: discord.Interaction[core.Genji],
        difficulty: app_commands.Choice[str] | None = None,
        minimum_rating: app_commands.Choice[int] | None = None,
        include_completed: bool = False,
    ):
        await itx.response.defer(ephemeral=True)
        embed = utils.GenjiEmbed(title="Map Search")
        embed.set_thumbnail(url=None)

        ranges = utils.TOP_DIFFICULTIES_RANGES.get(
            getattr(difficulty, "value", None), None
        )
        low_range = None if ranges is None else ranges[0]
        high_range = None if ranges is None else ranges[1]

        view_filter = {
            True: None,
            False: False,
        }
        maps = await self._base_map_search(
            itx,
            low_range=low_range,
            high_range=high_range,
            minimum_rating=int(getattr(minimum_rating, "value", 0)),
            view_filter=view_filter[include_completed],
        )
        if not maps:
            raise utils.NoMapsFoundError

        rand = random.randint(0, len(maps) - 1)
        maps = [maps[rand]]

        embeds = self.create_map_embeds(maps)
        view = views.Paginator(embeds, itx.user)
        await view.start(itx)

    @app_commands.command(name="map-search")
    @app_commands.choices(
        minimum_rating=utils.ALL_STARS_CHOICES,
        difficulty=[app_commands.Choice(name=x, value=x) for x in utils.DIFFICULTIES],
    )
    @app_commands.autocomplete(
        map_name=utils.autocomplete.map_name_autocomplete,
        map_type=utils.autocomplete.map_type_autocomplete,
        creator=utils.autocomplete.creator_autocomplete,
        mechanics=utils.autocomplete.map_mechanics_autocomplete,
        map_code=utils.autocomplete.map_codes_autocomplete,
    )
    @app_commands.guilds(
        discord.Object(id=utils.GUILD_ID), discord.Object(id=868981788968640554)
    )
    async def map_search(
        self,
        itx: discord.Interaction[core.Genji],
        map_name: app_commands.Transform[str, MapNameTransformer] | None = None,
        difficulty: app_commands.Choice[str] | None = None,
        map_code: app_commands.Transform[str, utils.MapCodeTransformer] | None = None,
        creator: app_commands.Transform[int, utils.CreatorTransformer] | None = None,
        mechanics: app_commands.Transform[str, MapMechanicsTransformer] | None = None,
        map_type: app_commands.Transform[str, MapTypeTransformer] | None = None,
        completed: typing.Literal["All", "Not Completed", "Completed"] = "All",
        only_playtest: bool = False,
        only_maps_with_medals: bool = False,
        minimum_rating: app_commands.Choice[int] | None = None,
    ) -> None:
        """
        Search for maps based on various filters.

        Args:
            itx: Interaction
            map_type: Type of parkour map
            map_name: Overwatch map
            creator: Creator name
            map_code: Specific map code
            difficulty: Difficulty filter
            mechanics: Mechanics filter
            minimum_rating: Show maps above a specific quality rating
            completed: Show completed maps, non completed maps or all
            only_playtest: Show only playtest maps
            only_maps_with_medals: Show only maps that have medals
        """
        await itx.response.defer(ephemeral=True)
        embed = utils.GenjiEmbed(title="Map Search")
        embed.set_thumbnail(url=None)

        ranges = utils.TOP_DIFFICULTIES_RANGES.get(
            getattr(difficulty, "value", None), None
        )
        low_range = None if ranges is None else ranges[0]
        high_range = None if ranges is None else ranges[1]

        view_filter = {
            "All": None,
            "Not Completed": False,
            "Completed": True,
        }
        maps = await self._base_map_search(
            itx,
            map_code,
            map_name,
            map_type,
            creator,
            low_range,
            high_range,
            mechanics,
            int(getattr(minimum_rating, "value", 0)),
            only_maps_with_medals,
            only_playtest,
            view_filter[completed],
        )
        if not maps:
            raise utils.NoMapsFoundError

        embeds = self.create_map_embeds(maps)

        view = views.Paginator(embeds, itx.user)
        await view.start(itx)

    @staticmethod
    async def _base_map_search(
        itx: discord.Interaction[core.Genji],
        map_code: str | None = None,
        map_name: str | None = None,
        map_type: str | None = None,
        creator: int | None = None,
        low_range: float | None = None,
        high_range: float | None = None,
        mechanics: str | None = None,
        minimum_rating: int | None = None,
        only_maps_with_medals: bool = False,
        only_playtest: bool = False,
        view_filter: bool | None = None,
    ):
        maps = []
        async for _map in itx.client.database.get(
            """
              WITH
                completions AS (
                  SELECT map_code, record, verified
                    FROM records
                   WHERE user_id = $10
                )

            SELECT
              am.map_name, map_type, am.map_code, am."desc", am.official,
              am.archived, guide, mechanics, restrictions, am.checkpoints,
              creators, difficulty, quality, creator_ids, am.gold, am.silver,
              am.bronze, p.thread_id, pa.count, pa.required_votes,
              c.map_code IS NOT NULL AS completed,
              CASE
                WHEN verified = TRUE AND c.record <= am.gold   THEN 'Gold'
                WHEN verified = TRUE AND c.record <= am.silver THEN 'Silver'
                WHEN verified = TRUE AND c.record <= am.bronze THEN 'Bronze'
                                                               ELSE ''
              END AS medal_type
              FROM
                all_maps am
                  LEFT JOIN completions c ON am.map_code = c.map_code
                  LEFT JOIN playtest p ON am.map_code = p.map_code AND p.is_author IS TRUE
                  LEFT JOIN playtest_avgs pa ON pa.map_code = am.map_code
             WHERE
                 ($1::text IS NULL OR am.map_code = $1)
             AND ($1::text IS NOT NULL OR ((archived = FALSE)
               AND (official = $11::bool)
               AND ($2::text IS NULL OR map_type LIKE $2)
               AND ($3::text IS NULL OR map_name = $3)
               AND ($4::text IS NULL OR mechanics LIKE $4)
               AND ($5::numeric(10, 2) IS NULL OR $6::numeric(10, 2) IS NULL OR (difficulty >= $5::numeric(10, 2)
                 AND difficulty < $6::numeric(10, 2)))
               AND ($7::int IS NULL OR quality >= $7)
               AND ($8::bigint IS NULL OR $8 = ANY (creator_ids))
               AND ($12::bool IS FALSE OR (gold IS NOT NULL AND silver IS NOT NULL AND bronze IS NOT NULL))))
             GROUP BY
               am.map_name, map_type, am.map_code, am."desc", am.official, am.archived, guide, mechanics,
               restrictions, am.checkpoints, creators, difficulty, quality, creator_ids, am.gold, am.silver,
               am.bronze, c.map_code IS NOT NULL, c.record, verified, p.thread_id, pa.count, pa.required_votes

            HAVING
              ($9::bool IS NULL OR c.map_code IS NOT NULL = $9)

             ORDER BY
               difficulty, quality DESC;
            """,
            map_code,
            wrap_string_with_percent(map_type),
            map_name,
            wrap_string_with_percent(mechanics),
            low_range,
            high_range,
            minimum_rating,
            creator,
            view_filter,
            itx.user.id,
            not only_playtest,
            only_maps_with_medals,
        ):
            maps.append(_map)
        return maps

    @staticmethod
    def create_map_embeds(
        maps: list[database.DotRecord],
    ) -> list[discord.Embed | utils.GenjiEmbed]:
        embed_list = []
        embed = utils.GenjiEmbed(title="Map Search")
        for i, _map in enumerate(maps):
            m = MapEmbedData(_map)
            embed.add_description_field(
                name=m.name,
                value=m.value,
            )
            if split_nth_iterable(current=i, iterable=maps, split=5):
                embed_list.append(embed)
                embed = utils.GenjiEmbed(title="Map Search")
        return embed_list
