from __future__ import annotations

import typing

import discord.ui

if typing.TYPE_CHECKING:
    import core
    import views
    from utils.models import Map


class MapSubmitSelection(discord.ui.Select):
    view: views.ConfirmBaseView

    async def callback(self, itx: discord.Interaction[core.Genji]) -> None:
        await itx.response.defer(ephemeral=True)
        for x in self.options:
            x.default = x.value in self.values
        await self.view.map_submit_enable()


class MapTypeSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map type(s)?",
            max_values=len(options),
        )


class DifficultySelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="What difficulty?",
        )


class MechanicsSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map mechanic(s)?",
            min_values=0,
            max_values=len(options),
        )


class RestrictionsSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map restriction(s)?",
            min_values=0,
            max_values=len(options),
        )

class MapSubmissionView(discord.ui.View):
    def __init__(self, data: Map) -> None:
        super().__init__()
        self._map = data

    def _setup(self):
