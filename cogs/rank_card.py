from __future__ import annotations

import asyncio
import os
import typing
from io import BytesIO

import discord
from discord import Interaction, app_commands
from discord.ext import commands
from playwright.async_api import async_playwright

from utils import constants, transformers, utils

if typing.TYPE_CHECKING:
    import core

GENJI_API_KEY: str = os.getenv("GENJI_API_KEY", "")
GENJI_PK_HTTP_USERNAME = os.getenv("GENJI_PK_HTTP_USERNAME", "")
GENJI_PK_HTTP_PASSWORD = os.getenv("GENJI_PK_HTTP_PASSWORD", "")


class RankCard(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    @app_commands.command(name="old-rank-card")
    @app_commands.guilds(constants.GUILD_ID, 968951072599187476)
    async def rank_card_old(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[discord.Member | utils.FakeUser, transformers.AllUserTransformer] | None,
    ) -> None:
        _user = user
        if user is None:
            _user = itx.user
        assert _user
        await itx.response.send_message(f"https://api.genji.pk/v1/rank_card/{_user.id}", ephemeral=True)

    @app_commands.command(name="rank_test")
    @app_commands.guilds(constants.GUILD_ID, 968951072599187476)
    async def rank_card_test(self, itx: Interaction, user: discord.Member | None = None) -> None:
        _user = user or itx.user
        create_url = f"https://test.genji.pk/api/rankcard/getRenderedRankcard.php?user_id={_user.id}"
        await self._rank_card(create_url, itx, user)

    @app_commands.command(name="rank-card")
    @app_commands.guilds(constants.GUILD_ID, 968951072599187476)
    async def rank_card(self, itx: Interaction, user: discord.Member | None = None) -> None:
        _user = user or itx.user
        create_url = f"https://genji.pk/api/rankcard/getRenderedRankcard.php?user_id={_user.id}"
        await self._rank_card(create_url, itx, user)

    @staticmethod
    async def _rank_card(create_url: str, itx: Interaction, user: discord.Member | None = None) -> None:
        await itx.response.defer(ephemeral=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                extra_http_headers={"X-API-KEY": GENJI_API_KEY},
                viewport={"width": 1400, "height": 700},
                http_credentials={"username": GENJI_PK_HTTP_USERNAME, "password": GENJI_PK_HTTP_PASSWORD},
            )
            page = await context.new_page()
            await page.goto(create_url)
            screenshot = await page.locator(".rank-card").screenshot(type="png", omit_background=True)
            image_buf = BytesIO(screenshot)
            image_buf.seek(0)
            await itx.edit_original_response(attachments=[discord.File(image_buf, filename="rank_card.png")])


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(RankCard(bot))
