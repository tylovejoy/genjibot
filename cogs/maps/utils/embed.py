from __future__ import annotations

import asyncpg
import discord

import utils


class MapEmbedData:
    def __init__(self, data: asyncpg.Record):
        self._data = data

    @property
    def _guides(self):
        res = ""
        if None not in self._data["guide"]:
            guides = [
                f"[{i}]({guide})" for i, guide in enumerate(self._data["guide"], 1)
            ]
            res = f"`Guide(s)` {', '.join(guides)}"
        return res

    @property
    def _medals(self):
        res = ""
        if self._data["gold"]:
            res = (
                f"`Medals` "
                f"{utils.FULLY_VERIFIED_GOLD} {self._data['gold']} | "
                f"{utils.FULLY_VERIFIED_SILVER} {self._data['silver']} | "
                f"{utils.FULLY_VERIFIED_BRONZE} {self._data['bronze']}"
            )
        return res

    @property
    def _completed(self):
        res = ""
        if self._data.get("completed", None):
            res = "🗸 Completed"
            if self._data["medal_type"]:
                res += " | 🗸 " + self._data["medal_type"]
        return res

    @property
    def _playtest(self):
        res = ""
        if self._data.get("official", None) and not self._data["official"]:
            res = (
                f"\n‼️**IN PLAYTESTING, SUBJECT TO CHANGE**‼️\n"
                f"Votes: {self._data['count']} / {self._data['required_votes']}\n"
                f"[Click here to go to the playtest thread]"
                f"(https://discord.com/channels/842778964673953812/{self._data['thread_id']})"
            )
        return res

    @property
    def _rating(self):
        return (
            f"`Rating` {utils.create_stars(self._data['quality'])}"
            if self._data.get("quality", None) and self._data["quality"]
            else "Unrated"
        )

    @property
    def _creator(self):
        return f"`Creator` {discord.utils.escape_markdown(self._data['creators'])}"

    @property
    def _map(self):
        return f"`Map` {self._data['map_name']}"

    @property
    def _difficulty(self):
        return (
            f"`Difficulty` {utils.convert_num_to_difficulty(self._data['difficulty'])}"
        )

    @property
    def _mechanics(self):
        return (
            f"`Mechanics` {self._data['mechanics']}"
            if self._data["mechanics"]
            else None
        )

    @property
    def _restrictions(self):
        return (
            f"`Restrictions` {self._data['restrictions']}"
            if self._data["restrictions"]
            else None
        )

    @property
    def _type(self):
        return f"`Type` {self._data['map_type']}" if self._data["map_type"] else None

    @property
    def _checkpoints(self):
        return (
            f"`Checkpoints` {self._data['checkpoints']}"
            if self._data["checkpoints"]
            else None
        )

    @property
    def _description(self):
        return f"`Desc` {self._data['desc']}" if self._data["desc"] else None

    @property
    def name(self):
        return f"{self._data['map_code']} {self._completed}"

    def _non_null_values(self):
        values = (
            self._rating,
            self._creator,
            self._map,
            self._difficulty,
            self._mechanics,
            self._restrictions,
            self._guides,
            self._type,
            self._checkpoints,
            self._medals,
            self._description,
        )
        return list(filter(None, values))

    @property
    def value(self):
        res = ""
        vals = self._non_null_values()
        last_idx = len(vals) - 1
        for i, val in enumerate(vals):
            if i == last_idx:
                res += f"┗ {val}"
            else:
                res += f"┣ {val}"
            res += "\n"

        return self._playtest + res
