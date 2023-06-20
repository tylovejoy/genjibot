from __future__ import annotations

import discord

import cogs.maps.utils.utils
import core
import utils
from cogs.maps.utils.mtea import MAP_DATA, DIFF_TO_RANK


async def new_map_newsfeed(
    client: core.Genji,
    user_id: int,
    data: cogs.maps.utils.utils.MapSubmission,
):
    nickname = client.cache.users[user_id].nickname
    embed = utils.GenjiEmbed(
        title=f"{nickname} has submitted a new {data.difficulty} map on {data.map_name}!\n",
        description=(
            f"Use the command `/map-search map_code:{data.map_code}` to see the details!"
        ),
        color=getattr(
            MAP_DATA.get(data.map_name, discord.Color.from_str("#000000")),
            "COLOR",
            discord.Color.from_str("#000000"),
        ),
    )
    embed.set_image(url=getattr(MAP_DATA.get(data.map_name, None), "IMAGE_URL", None))
    base_thumbnail_url = "http://207.244.249.145/assets/images/genji_ranks/"
    rank = DIFF_TO_RANK[
        data.difficulty.replace("+", "").replace("-", "").rstrip()
    ].lower()
    embed.set_thumbnail(url=f"{base_thumbnail_url}{rank}.png")
    await client.get_guild(utils.GUILD_ID).get_channel(utils.NEWSFEED).send(embed=embed)
