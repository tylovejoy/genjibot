from __future__ import annotations

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

GENJI_API_KEY = os.getenv("GENJI_API_KEY")


class RankCard(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    @app_commands.command(name="rank-card")
    @app_commands.guilds(constants.GUILD_ID, 968951072599187476)
    async def rank_card(
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
    async def rank_test(self, itx: Interaction, user: discord.Member | None = None) -> None:
        await itx.response.defer(ephemeral=True)
        _user = user or itx.user

        create_url = f"https://test.genji.pk/api/rankcard/getRenderedRankcard.php?user_id={_user.id}"

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(extra_http_headers={"X-API-KEY": GENJI_API_KEY})
            await page.goto(create_url)
            screenshot = await page.locator(".rank-card").screenshot(type="png", omit_background=True)
            image_buf = BytesIO(screenshot)
            image_buf.seek(0)
            await itx.edit_original_response(attachments=[discord.File(image_buf, filename="rank_card.png")])
            await browser.close()


async def setup(bot: core.Genji) -> None:
    """Add Cog to Discord bot."""
    await bot.add_cog(RankCard(bot))
