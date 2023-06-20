from __future__ import annotations

import dataclasses
import re

import discord

_MAPS_BASE_URL = "http://207.244.249.145/assets/images/map_banners/"


@dataclasses.dataclass
class MapMetadata:
    NAME: str
    COLOR: discord.Color
    IMAGE_URL: str = ""

    def __post_init__(self):
        self.IMAGE_URL = _MAPS_BASE_URL + self._remove_extra_chars(self.NAME) + ".png"

    def _remove_extra_chars(self, string: str):
        return re.sub(r"[\s:()\']", "", string.lower())


all_map_constants = [
    MapMetadata("Antarctic Peninsula", discord.Color.from_str("#29A0CC")),
    MapMetadata("Ayutthaya", discord.Color.gold()),
    MapMetadata("Black Forest", discord.Color.from_str("#94511C")),
    MapMetadata("Blizzard World", discord.Color.from_str("#39AAFF")),
    MapMetadata("Busan", discord.Color.from_str("#FF9F00")),
    MapMetadata("Castillo", discord.Color.from_str("#E13C3C")),
    MapMetadata("Chateau Guillard", discord.Color.from_str("#BCBCBC")),
    MapMetadata("Circuit Royal", discord.Color.from_str("#00008B")),
    MapMetadata("Colosseo", discord.Color.from_str("#BF7F00")),
    MapMetadata("Dorado", discord.Color.from_str("#008a8a")),
    MapMetadata("Ecopoint: Antarctica", discord.Color.from_str("#29A0CC")),
    MapMetadata("Eichenwalde", discord.Color.from_str("#53E500")),
    MapMetadata("Esperanca", discord.Color.from_str("#7BD751")),
    MapMetadata("Hanamura", discord.Color.from_str("#EF72A3")),
    MapMetadata("Havana", discord.Color.from_str("#00D45B")),
    MapMetadata("Hollywood", discord.Color.from_str("#FFFFFF")),
    MapMetadata("Horizon Lunar Colony ", discord.Color.from_str("#000000")),
    MapMetadata("Ilios", discord.Color.from_str("#008FDF")),
    MapMetadata("Junkertown", discord.Color.from_str("#EC9D00")),
    MapMetadata("Kanezaka", discord.Color.from_str("#DF3A4F")),
    MapMetadata("King's Row", discord.Color.from_str("#105687")),
    MapMetadata("Lijiang Tower", discord.Color.from_str("#169900")),
    MapMetadata("Malevento", discord.Color.from_str("#DDD816")),
    MapMetadata("Midtown", discord.Color.from_str("#BCBCBC")),
    MapMetadata("Necropolis", discord.Color.from_str("#409C00")),
    MapMetadata("Nepal", discord.Color.from_str("#93C0C7")),
    MapMetadata("New Queen Street", discord.Color.from_str("#CD1010")),
    MapMetadata("Numbani", discord.Color.from_str("#3F921B")),
    MapMetadata("Oasis", discord.Color.from_str("#C98600")),
    MapMetadata("Paraiso", discord.Color.from_str("#19FF00")),
    MapMetadata("Paris", discord.Color.from_str("#6260DA")),
    MapMetadata("Petra", discord.Color.from_str("#DDD816")),
    MapMetadata("Practice Range", discord.Color.from_str("#000000")),
    MapMetadata("Rialto", discord.Color.from_str("#21E788")),
    MapMetadata("Route 66", discord.Color.from_str("#FF9E2F")),
    MapMetadata("Shambali", discord.Color.from_str("#2986CC")),
    MapMetadata("Temple of Anubis", discord.Color.from_str("#D25E00")),
    MapMetadata("Volskaya Industries", discord.Color.from_str("#8822DC")),
    MapMetadata("Watchpoint: Gibraltar", discord.Color.from_str("#BCBCBC")),
    MapMetadata("Workshop Chamber", discord.Color.from_str("#000000")),
    MapMetadata("Workshop Expanse", discord.Color.from_str("#000000")),
    MapMetadata("Workshop Green Screen", discord.Color.from_str("#3BB143")),
    MapMetadata("Workshop Island", discord.Color.from_str("#000000")),
    MapMetadata("Framework", discord.Color.from_str("#000000")),
    MapMetadata("Tools", discord.Color.from_str("#000000")),
    MapMetadata("Talantis", discord.Color.from_str("#1AA7EC")),
    MapMetadata("Chateau Guillard (Halloween)", discord.Color.from_str("#BCBCBC")),
    MapMetadata("Eichenwalde (Halloween)", discord.Color.from_str("#53E500")),
    MapMetadata("Hollywood (Halloween)", discord.Color.from_str("#FFFFFF")),
    MapMetadata("Black Forest (Winter)", discord.Color.from_str("#94511C")),
    MapMetadata("Blizzard World (Winter)", discord.Color.from_str("#39AAFF")),
    MapMetadata("Ecopoint: Antarctica (Winter)", discord.Color.from_str("#29A0CC")),
    MapMetadata("Hanamura (Winter)", discord.Color.from_str("#EF72A3")),
    MapMetadata("King's Row (Winter)", discord.Color.from_str("#105687")),
    MapMetadata("Busan (Lunar New Year)", discord.Color.from_str("#FF9F00")),
    MapMetadata("Lijiang Tower (Lunar New Year)", discord.Color.from_str("#169900")),
]
MAP_DATA: dict[str, MapMetadata] = {const.NAME: const for const in all_map_constants}
DIFF_TO_RANK = {
    "Beginner": "Ninja",
    "Easy": "Jumper",
    "Medium": "Skilled",
    "Hard": "Pro",
    "Very Hard": "Master",
    "Extreme": "Grandmaster",
    "Hell": "God",
}
