from __future__ import annotations

import random
import typing

import discord
from discord import app_commands
from discord.ext import commands

import views
from utils import constants, embeds, errors, map_submission, maps, ranks, transformers, utils
from utils.newsfeed import NewsfeedEvent

if typing.TYPE_CHECKING:
    import core
    import database


class Maps(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    _map_maker = app_commands.Group(
        name="map-maker",
        guild_ids=[constants.GUILD_ID],
        description="Map maker only commands",
    )

    _creator = app_commands.Group(
        name="creator",
        guild_ids=[constants.GUILD_ID],
        description="Edit creators",
        parent=_map_maker,
    )

    @app_commands.command(name="submit-map")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    async def submit_map(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, transformers.MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, transformers.RecordTransformer] | None = None,
        silver: app_commands.Transform[float, transformers.RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, transformers.RecordTransformer] | None = None,
    ) -> None:
        """Submit your map to get play tested.

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

        submission = maps.MapSubmission(
            itx.user,
            map_code,
            map_name,
            checkpoint_count,
            description,
            medals,
            guides=[guide_url],
        )
        await map_submission.submit_map_(
            itx,
            submission,
        )

    @app_commands.command(name="random-map")
    @app_commands.choices(
        minimum_rating=constants.ALL_STARS_CHOICES,
        difficulty=[app_commands.Choice(name=x, value=x) for x in ranks.DIFFICULTIES],
    )
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID), discord.Object(id=868981788968640554))
    async def random_map(
        self,
        itx: discord.Interaction[core.Genji],
        difficulty: app_commands.Choice[str] | None = None,
        minimum_rating: app_commands.Choice[int] | None = None,
        include_completed: bool = False,
    ) -> None:
        await itx.response.defer(ephemeral=True)
        embed = embeds.GenjiEmbed(title="Map Search")
        embed.set_thumbnail(url=None)

        ranges = ranks.TOP_DIFFICULTIES_RANGES.get(getattr(difficulty, "value", None), None)
        low_range = None if ranges is None else ranges[0]
        high_range = None if ranges is None else ranges[1]

        view_filter = {
            True: None,
            False: False,
        }
        _maps = await self._base_map_search(
            itx,
            low_range=low_range,
            high_range=high_range,
            minimum_rating=int(getattr(minimum_rating, "value", 0)),
            view_filter=view_filter[include_completed],
        )
        if not _maps:
            raise errors.NoMapsFoundError

        rand = random.randint(0, len(_maps) - 1)
        _maps = [_maps[rand]]

        _embeds = self.create_map_embeds(_maps)
        view = views.Paginator(_embeds, itx.user)
        await view.start(itx)

    @app_commands.command(name="map-search")
    @app_commands.choices(
        minimum_rating=constants.ALL_STARS_CHOICES,
        difficulty=[app_commands.Choice(name=x, value=x) for x in ranks.DIFFICULTIES],
    )
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID), discord.Object(id=868981788968640554))
    async def map_search(
        self,
        itx: discord.Interaction[core.Genji],
        map_name: app_commands.Transform[str, transformers.MapNameTransformer] | None = None,
        difficulty: app_commands.Choice[str] | None = None,
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer] | None = None,
        creator: app_commands.Transform[int, transformers.CreatorTransformer] | None = None,
        mechanics: (app_commands.Transform[str, transformers.MapMechanicsTransformer] | None) = None,
        restrictions: (app_commands.Transform[str, transformers.MapRestrictionsTransformer] | None) = None,
        map_type: app_commands.Transform[str, transformers.MapTypesTransformer] | None = None,
        completed: typing.Literal["All", "Not Completed", "Completed"] = "All",
        only_playtest: bool = False,
        only_maps_with_medals: bool = False,
        minimum_rating: app_commands.Choice[int] | None = None,
    ) -> None:
        """Search for maps based on various filters.

        Args:
            itx: Interaction
            map_type: Type of parkour map
            map_name: Overwatch map
            creator: Creator name
            map_code: Specific map code
            difficulty: Difficulty filter
            mechanics: Mechanics filter
            restrictions: Restrictions filter
            minimum_rating: Show maps above a specific quality rating
            completed: Show completed maps, non completed maps or all
            only_playtest: Show only playtest maps
            only_maps_with_medals: Show only maps that have medals

        """
        await itx.response.defer(ephemeral=True)
        embed = embeds.GenjiEmbed(title="Map Search")
        embed.set_thumbnail(url=None)

        ranges = ranks.TOP_DIFFICULTIES_RANGES.get(getattr(difficulty, "value", None), None)
        low_range = None if ranges is None else ranges[0]
        high_range = None if ranges is None else ranges[1]

        view_filter = {
            "All": None,
            "Not Completed": False,
            "Completed": True,
        }
        _maps = await self._base_map_search(
            itx,
            map_code,
            map_name,
            map_type,
            creator,
            low_range,
            high_range,
            mechanics,
            restrictions,
            int(getattr(minimum_rating, "value", 0)),
            only_maps_with_medals,
            only_playtest,
            view_filter[completed],
        )
        if not _maps:
            raise errors.NoMapsFoundError

        _embeds = self.create_map_embeds(_maps)

        view = views.Paginator(_embeds, itx.user)
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
        restrictions: str | None = None,
        minimum_rating: int | None = None,
        only_maps_with_medals: bool = False,
        only_playtest: bool = False,
        view_filter: bool | None = None,
    ) -> list[database.DotRecord]:
        _maps: list[database.DotRecord | None] = []
        async for _map in itx.client.database.get(
            """
              WITH
                completions AS (
                    SELECT DISTINCT ON (map_code)
                        map_code,
                        record,
                        verified,
                        inserted_at
                    FROM records
                    WHERE user_id = $10 AND legacy IS FALSE
                    ORDER BY map_code, inserted_at DESC
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
               AND ($13::text IS NULL OR restrictions LIKE $13)
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
            utils.wrap_string_with_percent(map_type),
            map_name,
            utils.wrap_string_with_percent(mechanics),
            low_range,
            high_range,
            minimum_rating,
            creator,
            view_filter,
            itx.user.id,
            not only_playtest,
            only_maps_with_medals,
            utils.wrap_string_with_percent(restrictions),
        ):
            _maps.append(_map)
        return _maps

    @staticmethod
    def create_map_embeds(
        _maps: list[database.DotRecord],
    ) -> list[discord.Embed | embeds.GenjiEmbed]:
        embed_list = []
        embed = embeds.GenjiEmbed(title="Map Search")
        for i, _map in enumerate(_maps):
            m = maps.MapEmbedData(_map)
            embed.add_description_field(
                name=m.name,
                value=m.value,
            )
            if utils.split_nth_iterable(current=i, iterable=_maps, split=5):
                embed_list.append(embed)
                embed = embeds.GenjiEmbed(title="Map Search")
        return embed_list

    @staticmethod
    def display_official(official: bool) -> str:
        return (
            (
                "┃<:_:998055526468423700>"
                "<:_:998055528355860511>"
                "<:_:998055530440437840>"
                "<:_:998055532030079078>"
                "<:_:998055534068510750>"
                "<:_:998055536346021898>\n"
                "┃<:_:998055527412142100>"
                "<:_:998055529219887154>"
                "<:_:998055531346415656>"
                "<:_:998055533225455716>"
                "<:_:998055534999654480>"
                "<:_:998055537432338532>\n"
            )
            if official
            else ""
        )

    @app_commands.command(name="guide")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    async def view_guide(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        """View guides that have been submitted for a particular map.

        Args:
            map_code: Overwatch share code
            itx: Interaction

        """
        await itx.response.defer(ephemeral=False)
        if not await self.bot.database.is_existing_map_code(map_code):
            raise errors.InvalidMapCodeError

        guides = [
            x
            async for x in itx.client.database.get(
                "SELECT url FROM guides WHERE map_code=$1",
                map_code,
            )
        ]
        guides = [x.url for x in guides]
        if not guides:
            raise errors.NoGuidesExistError

        view = views.Paginator(guides, itx.user)
        await view.start(itx)

    @app_commands.command(name="add-guide")
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    async def add_guide(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        url: app_commands.Transform[str, transformers.URLTransformer],
    ) -> None:
        """Add a guide for a particular map.

        Args:
            map_code: Overwatch share code
            itx: Interaction
            url: URL for guide

        """
        await itx.response.defer(ephemeral=True)
        if not await self.bot.database.is_existing_map_code(map_code):
            raise errors.InvalidMapCodeError

        guides = [
            x
            async for x in itx.client.database.get(
                "SELECT url FROM guides WHERE map_code=$1",
                map_code,
            )
        ]
        guides = [x.url for x in guides]

        if url in guides:
            raise errors.GuideExistsError

        view = views.Confirm(itx, ephemeral=True)
        await itx.edit_original_response(
            content=f"Is this correct?\nMap code: {map_code}\nURL: {url}",
            view=view,
        )
        await view.wait()

        if not view.value:
            return

        await itx.client.database.set(
            "INSERT INTO guides (map_code, url) VALUES ($1, $2)",
            map_code,
            url,
        )
        nickname = await itx.client.database.fetch_nickname(itx.user.id)
        _data = {
            "user": {
                "user_id": itx.user.id,
                "nickname": nickname,
            },
            "map": {
                "map_code": map_code,
                "guide": [url],
            },
        }
        event = NewsfeedEvent("guide", _data)
        await itx.client.genji_dispatch.handle_event(event, itx.client)

    @app_commands.command()
    @app_commands.choices(
        quality=[
            app_commands.Choice(
                name=constants.ALL_STARS[x - 1],
                value=x,
            )
            for x in range(1, 7)
        ]
    )
    @app_commands.guilds(discord.Object(id=constants.GUILD_ID))
    async def rate(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        quality: app_commands.Choice[int],
    ) -> None:
        await itx.response.defer(ephemeral=True)
        if (
            await itx.client.database.get_row(
                "SELECT exists(SELECT 1 FROM map_creators WHERE map_code = $1 AND user_id = $2)",
                map_code,
                itx.user.id,
            )
        ).get("exists", None):
            raise errors.CannotRateOwnMapError

        row = await itx.client.database.get_row(
            "SELECT exists(SELECT 1 FROM records WHERE map_code = $1 AND user_id = $2)",
            map_code,
            itx.user.id,
        )
        if not row.exists:
            raise errors.NoCompletionFoundError

        view = views.Confirm(itx)
        await itx.edit_original_response(
            content=f"You want to rate {map_code} *{quality.value}* stars ({quality.name}). Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            """
                INSERT INTO map_ratings (user_id, map_code, quality)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, map_code)
                DO UPDATE SET quality = excluded.quality
            """,
            itx.user.id,
            map_code,
            quality.value,
        )


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(Maps(bot))
