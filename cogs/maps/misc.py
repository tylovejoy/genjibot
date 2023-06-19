from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import utils
import views

if typing.TYPE_CHECKING:
    import core


class MapsMisc(commands.Cog):
    """Miscellaneous map commands"""

    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="guide")
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def view_guide(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        """
        View guides that have been submitted for a particular map.

        Args:
            map_code: Overwatch share code
            itx: Interaction
        """
        await itx.response.defer(ephemeral=False)
        if map_code not in itx.client.cache.maps.keys:
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
        itx: discord.Interaction[core.Genji],
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
        if map_code not in itx.client.cache.maps.keys:
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

    @app_commands.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    @app_commands.choices(
        quality=[
            app_commands.Choice(
                name=utils.ALL_STARS[x - 1],
                value=x,
            )
            for x in range(1, 7)
        ]
    )
    @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    async def rate(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        quality: app_commands.Choice[int],
    ):
        await itx.response.defer(ephemeral=True)
        if (
            await itx.client.database.get_row(
                "SELECT exists(SELECT 1 FROM map_creators WHERE map_code = $1 AND user_id = $2)",
                map_code,
                itx.user.id,
            )
        ).get("exists", None):
            raise utils.CannotRateOwnMap

        row = await itx.client.database.get_row(
            "SELECT exists(SELECT 1 FROM records WHERE map_code = $1 AND user_id = $2)",
            map_code,
            itx.user.id,
        )
        if not row.exists:
            raise utils.NoCompletionFoundError

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
            DO UPDATE SET quality = excluded.quality""",
            itx.user.id,
            map_code,
            quality.value,
        )
