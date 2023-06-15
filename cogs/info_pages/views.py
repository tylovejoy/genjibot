from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord.ui

from cogs.info_pages.completions_embeds import (
    COMPLETION_SUBMISSION_RULES,
    COMPLETION_SUBMISSIONS_INFO,
    MEDALS_INFO,
    RANKS_INFO,
)
from cogs.info_pages.maps_embeds import (
    DIFF_TECH_CHART,
    MAP_PLAYTESTING_INFO,
    MAP_SUBMISSIONS_INFO,
)

if TYPE_CHECKING:
    import core


class InfoButton(discord.ui.Button):
    def __init__(
        self,
        label: str,
        content: discord.Embed,
        emoji: discord.Emoji | discord.PartialEmoji | str | None = None,
        row: int = 0,
    ):
        super().__init__(
            style=discord.ButtonStyle.grey,
            label=label,
            custom_id=re.sub(r"[\s:()?!&\']", "", label.lower()),
            emoji=emoji,
            row=row,
        )
        self.content = content

    async def callback(self, itx: discord.Interaction[core.Genji]):
        await itx.response.send_message(embed=self.content, ephemeral=True)


class CompletionInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(InfoButton("How to submit?", COMPLETION_SUBMISSIONS_INFO))
        self.add_item(InfoButton("Submission Rules", COMPLETION_SUBMISSION_RULES))
        self.add_item(InfoButton("Rank Info & Thresholds", RANKS_INFO))
        self.add_item(InfoButton("Medals Info & Thresholds", MEDALS_INFO))


class MapInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(InfoButton("How to submit?", MAP_SUBMISSIONS_INFO))
        self.add_item(InfoButton("Playtesting Info", MAP_PLAYTESTING_INFO))
        self.add_item(InfoButton("Difficulty & Techs Info", DIFF_TECH_CHART))
