from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import database
import utils
import views

if typing.TYPE_CHECKING:
    import core


class Maps(commands.Cog):
    """Maps"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    _map_maker = app_commands.Group(
        name="map-maker",
        guild_ids=[utils.GUILD_ID],
        description="Map maker only commands",
    )

    _creator = app_commands.Group(
        name="creator",
        guild_ids=[utils.GUILD_ID],
        description="Edit creators",
        parent=_map_maker,
    )

    # @_creator.command(name="remove")
    # @app_commands.autocomplete(
    #     map_code=cogs.map_codes_autocomplete,
    #     creator=cogs.users_autocomplete,
    # )
    # async def remove_creator(
    #     self,
    #     itx: core.Interaction[core.Genji],
    #     map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    #     creator: app_commands.Transform[int, utils.CreatorTransformer],
    # ) -> None:
    #     """Remove a creator from a map."""
    #     await cogs.remove_creator_(creator, itx, map_code)

    # @_creator.command(name="add")
    # @app_commands.autocomplete(
    #     map_code=cogs.map_codes_autocomplete,
    #     creator=cogs.users_autocomplete,
    # )
    # async def add_creator(
    #     self,
    #     itx: core.Interaction[core.Genji],
    #     map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    #     creator: app_commands.Transform[int, utils.CreatorTransformer],
    # ) -> None:
    #     await cogs.add_creator_(creator, itx, map_code)

    @app_commands.command(name="submit-map")
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    @app_commands.autocomplete(map_name=cogs.map_name_autocomplete)
    async def submit_map(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, utils.MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, utils.RecordTransformer] | None = None,
        silver: app_commands.Transform[float, utils.RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, utils.RecordTransformer] | None = None,
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
        await cogs.submit_map_(
            itx,
            itx.user,
            map_code,
            map_name,
            checkpoint_count,
            description,
            guide_url,
            medals,
        )

    @app_commands.command(name="map-search")
    @app_commands.choices(
        minimum_rating=utils.ALL_STARS_CHOICES,
        # [
        #     app_commands.Choice(name=str(x), value=x) for x in range(0, 6)
        # ],
        difficulty=[app_commands.Choice(name=x, value=x) for x in utils.DIFFICULTIES],
    )
    @app_commands.autocomplete(
        map_name=cogs.map_name_autocomplete,
        map_type=cogs.map_type_autocomplete,
        creator=cogs.creator_autocomplete,
        mechanics=cogs.map_mechanics_autocomplete,
        map_code=cogs.map_codes_autocomplete,
    )
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def map_search(
        self,
        itx: core.Interaction[core.Genji],
        map_type: app_commands.Transform[str, utils.MapTypeTransformer] | None = None,
        map_name: app_commands.Transform[str, utils.MapNameTransformer] | None = None,
        creator: app_commands.Transform[int, utils.CreatorTransformer] | None = None,
        difficulty: app_commands.Choice[str] | None = None,
        mechanics: app_commands.Transform[str, utils.MapMechanicsTransformer]
        | None = None,
        minimum_rating: app_commands.Choice[int] = None,
        map_code: app_commands.Transform[str, utils.MapCodeTransformer] | None = None,
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
        """
        await itx.response.defer(ephemeral=True)
        embed = utils.GenjiEmbed(title="Map Search")
        embed.set_thumbnail(url=None)
        maps: list[database.DotRecord | None] = []

        ranges = utils.TOP_DIFFICULTIES_RANGES.get(getattr(difficulty, "value", None), None)
        low_range = None if ranges is None else ranges[0]
        high_range = None if ranges is None else ranges[1]
        async for _map in itx.client.database.get(
            """
                WITH all_maps AS (SELECT map_name,
                    array_to_string((map_type), ', ')     AS map_type,
                    m.map_code,
                    "desc",
                    official,
                    archived,
                    array_agg(DISTINCT url)               AS guide,
                    array_to_string(array_agg(DISTINCT mech.mechanic), ', ') AS mechanics,
                    array_to_string(array_agg(DISTINCT rest.restriction), ', ') AS restrictions,
                    --array_to_string(SELECT name FROM map_techs LEFT JOIN unnest(mechanics), ', ')    AS mechanics,
                    --array_to_string((restrictions), ', ') AS restrictions,
                    checkpoints,
                    string_agg(DISTINCT (nickname), ', ') AS creators,
                    COALESCE(AVG(difficulty), 0)          AS difficulty,
                    COALESCE(AVG(quality), 0)             AS quality,
                    array_agg(DISTINCT mc.user_id)        AS creator_ids,
                    gold,
                    silver,
                    bronze
                    FROM maps m
                    LEFT JOIN map_mechanics mech on mech.map_code = m.map_code
                    LEFT JOIN map_restrictions rest on rest.map_code = m.map_code
                    LEFT JOIN map_creators mc on m.map_code = mc.map_code
                    LEFT JOIN users u on mc.user_id = u.user_id
                    LEFT JOIN map_ratings mr on mc.user_id = mr.user_id
                    LEFT JOIN guides g on m.map_code = g.map_code
                    LEFT JOIN map_medals mm on m.map_code = mm.map_code
                    GROUP BY checkpoints, map_name,
                    m.map_code, "desc", official, map_type, gold, silver, bronze, archived)
                SELECT *
                FROM all_maps
                WHERE
                (official = TRUE) AND
                (archived = FALSE) AND
                ($1::text IS NULL OR map_code = $1) AND
                ($2::text IS NULL OR map_type LIKE $2) AND
                ($3::text IS NULL OR map_name = $3) AND
                ($4::text IS NULL OR mechanics LIKE $4) AND
                (($5::numeric(10, 2) IS NULL OR difficulty >= $5) AND
                ($6::numeric(10, 2) IS NULL OR difficulty < $6)) AND
                ($7::int IS NULL OR quality >= $7) AND
                ($8::bigint IS NULL OR $8 = ANY(creator_ids))
                ORDER BY difficulty, quality DESC;
            """,
            map_code,
            map_type,
            map_name,
            mechanics,
            low_range,
            high_range,
            int(getattr(minimum_rating, "value", 0)),
            creator,
        ):
            maps.append(_map)
        if not maps:
            raise utils.NoMapsFoundError

        embeds = self.create_map_embeds(maps)

        view = views.Paginator(embeds, itx.user, None)
        await view.start(itx)

    @staticmethod
    def create_map_embeds(
        maps: list[database.DotRecord],
    ) -> list[discord.Embed | utils.GenjiEmbed]:
        embed_list = []
        embed = utils.GenjiEmbed(title="Map Search")
        for i, _map in enumerate(maps):
            guide_txt = ""
            medals_txt = ""
            if None not in _map.guide:
                guides = [f"[{j}]({guide})" for j, guide in enumerate(_map.guide, 1)]
                guide_txt = f"┣ `Guide(s)` {', '.join(guides)}\n"
            if _map.gold:
                medals_txt = (
                    f"┣ `Medals` "
                    f"{utils.FULLY_VERIFIED_GOLD} {_map.gold} | "
                    f"{utils.FULLY_VERIFIED_SILVER} {_map.silver} | "
                    f"{utils.FULLY_VERIFIED_BRONZE} {_map.bronze}\n"
                )
            embed.add_description_field(
                name=f"{_map.map_code}",
                value=(
                    f"┣ `Rating` {utils.create_stars(_map.quality)}\n"
                    f"┣ `Creator` {discord.utils.escape_markdown(_map.creators)}\n"
                    f"┣ `Map` {_map.map_name}\n"
                    f"┣ `Difficulty` {utils.convert_num_to_difficulty(_map.difficulty)}\n"
                    f"┣ `Mechanics` {_map.mechanics}\n"
                    f"┣ `Restrictions` {_map.restrictions}\n"
                    f"{guide_txt}"
                    f"┣ `Type` {_map.map_type}\n"
                    f"┣ `Checkpoints` {_map.checkpoints}\n"
                    f"{medals_txt}"
                    f"┗ `Desc` {_map.desc}"
                ),
            )
            if (
                (i != 0 and i % 5 == 0)
                or (i == 0 and len(maps) == 1)
                or i == len(maps) - 1
            ):
                embed_list.append(embed)
                embed = utils.GenjiEmbed(title="Map Search")
        return embed_list

    @staticmethod
    def display_official(official: bool):
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
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def view_guide(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        """
        View guides that have been submitted for a particular map.

        Args:
            map_code: Overwatch share code
            itx: Interaction
        """
        await itx.response.defer(ephemeral=False)
        if map_code not in itx.client.map_cache.keys():
            raise utils.InvalidMapCodeError

        guides = [
            x
            async for x in itx.client.database.get(
                "SELECT url FROM guides WHERE map_code=$1",
                map_code,
            )
        ]
        guides = [x.url for x in guides]
        if not guides:
            raise utils.NoGuidesExistError

        view = views.Paginator(guides, itx.user)
        await view.start(itx)

    @app_commands.command(name="add-guide")
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def add_guide(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        url: app_commands.Transform[str, utils.URLTransformer],
    ):
        """
        Add a guide for a particular map.

        Args:
            map_code: Overwatch share code
            itx: Interaction
            url: URL for guide
        """
        await itx.response.defer(ephemeral=True)
        if map_code not in itx.client.map_cache.keys():
            raise utils.InvalidMapCodeError

        guides = [
            x
            async for x in itx.client.database.get(
                "SELECT url FROM guides WHERE map_code=$1",
                map_code,
            )
        ]
        guides = [x.url for x in guides]

        if url in guides:
            raise utils.GuideExistsError

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
        itx.client.dispatch("newsfeed_guide", itx, itx.user, url, map_code)


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(Maps(bot))
