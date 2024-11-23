from __future__ import annotations

import datetime
from abc import ABC, abstractmethod

import discord
import msgspec

from . import constants, ranks, records


class _EmbedFormatter:
    @staticmethod
    def _wrap_str_code_block(value: str) -> str:
        return f"`{value}`"

    @staticmethod
    def _formatting_character(value: bool) -> str:
        if value:
            return "┣"
        return "┗"

    @classmethod
    def format(cls, values: dict[str, str]) -> str:
        res = ""
        filtered_values = {
            k: v
            for k, v in values.items()
            if v is not False and v is not None and v != ""
        }.items()
        length = len(filtered_values)
        for i, (name, value) in enumerate(filtered_values):
            if not name.startswith("_"):
                char = cls._formatting_character(i + 1 < length)
                wrapped_name = cls._wrap_str_code_block(name)
                res += f"{char} {wrapped_name} {value}\n"
            else:
                res += value + "\n"
        return res


class EmbedDataStrategy(ABC):
    def __init__(self, **kwargs):
        self.extra_params = kwargs

    @abstractmethod
    def create_embed_data(self, record: Record) -> dict:
        pass

    @abstractmethod
    def create_embed_title(self) -> str:
        pass


class CompletionLeaderboardStrategy(EmbedDataStrategy):
    def __init__(self, *, map_code: str, difficulty: str, legacy: bool = False):
        super().__init__(map_code=map_code, difficulty=difficulty, legacy=legacy)
        self.map_code = map_code
        self.difficulty = difficulty
        self.legacy = legacy

    def create_embed_data(self, record: Record) -> dict:
        return {
            "_rank": f"**{record.placement_string} - {record.nickname}**",
            "Time": record.record_screenshot_link + " " + record.icon_generator,
            "Video": record.video_link if record.video else None,
        }

    def create_embed_title(self) -> str:
        _title = "Leaderboard"
        if self.legacy:
            _title = "Legacy " + _title
        return f"{_title} - {self.map_code} - {self.difficulty}"


class PersonalRecordStrategy(EmbedDataStrategy):
    def __init__(self, *, user_nickname: str, filter_type: str):
        super().__init__(user_nickname=user_nickname, filter_type=filter_type)
        self.user_nickname = user_nickname
        self.filter_type = filter_type

    def create_embed_data(self, record: Record) -> dict:
        return {
            "_title": f"**{record.map_name} by {record.first_creator} ({record.map_code})**",
            "Difficulty": record.difficulty_string,
            "Time": record.record_screenshot_link + " " + record.icon_generator,
            "Video": record.video_link if record.video else None,
        }

    def create_embed_title(self) -> str:
        return f"Personal Records ({self.filter_type}) - {self.user_nickname}"


class RecordSubmissionStrategy(EmbedDataStrategy):
    def __init__(self):
        super().__init__()

    def create_embed_data(self, record: Record) -> dict:
        return {
            "Code": record.map_code,
            "Difficulty": record.difficulty_string,
            "Time": record.record_screenshot_link + " " + record.icon_generator,
            "Video": record.video_link if record.video else None,
        }

    def create_embed_title(self) -> str:
        return "New Submission!"


class Map(msgspec.Struct): ...


class Record(msgspec.Struct, kw_only=True):
    map_code: str | None = None
    user_id: int | None = None
    record: float | None = None
    screenshot: str | None = None
    nickname: str | None = None
    difficulty: float | None = None
    completion: bool | None = None
    verified: bool | None = None
    latest: int | None = None
    rank_num: int | None = None
    channel_id: int | None = None
    message_id: int | None = None
    creators: list[str] | None = None
    video: str | None = None
    hidden_id: int | None = None
    map_name: str | None = None
    gold: float | None = None
    silver: float | None = None
    bronze: float | None = None
    official: bool | None = None
    inserted_at: datetime.datetime | None = None
    verified_by: int | None = None

    @property
    def video_link(self) -> str:
        return f"[Link]({self.video})"

    @property
    def difficulty_string(self) -> str:
        return ranks.convert_num_to_difficulty(self.difficulty)

    @property
    def record_screenshot_link(self) -> str:
        time = self.record if not self.completion else "Completion"
        return f"[{time}]({self.screenshot})"

    @property
    def placement_string(self) -> str:
        # return f"{utils.PLACEMENTS.get(self.rank_num, '')} {make_ordinal(self.rank_num)}" TODO
        return f"{records.make_ordinal(self.rank_num)}"

    @property
    def first_creator(self) -> str:
        if self.creators:
            return self.creators[0]
        return ""

    @property
    def icon_generator(self) -> str:
        icon = ""
        if not self.gold or not self.silver or not self.bronze:
            return icon
        if self.video and not self.completion:
            if self.record < self.gold:
                if self.rank_num == 1:
                    icon = constants.GOLD_WR
                else:
                    icon = constants.FULLY_VERIFIED_GOLD
            elif self.record < self.silver:
                if self.rank_num == 1:
                    icon = constants.SILVER_WR
                else:
                    icon = constants.FULLY_VERIFIED_SILVER
            elif self.record < self.bronze:
                if self.rank_num == 1:
                    icon = constants.BRONZE_WR
                else:
                    icon = constants.FULLY_VERIFIED_BRONZE
            elif self.rank_num == 1:
                icon = constants.NON_MEDAL_WR
            else:
                icon = constants.FULLY_VERIFIED
        elif not self.completion:
            icon = constants.PARTIAL_VERIFIED
        return icon

    @classmethod
    def build_embeds(
        cls, _records: list[Record], *, strategy: EmbedDataStrategy
    ) -> list[discord.Embed]:
        descriptions = [strategy.create_embed_data(record) for record in _records]
        formatted_descriptions = [_EmbedFormatter.format(data) for data in descriptions]
        chunks = discord.utils.as_chunks(formatted_descriptions, 10)
        return [
            discord.Embed(
                title=strategy.create_embed_title(), description="\n".join(chunk)
            )
            for chunk in chunks
        ]

    @classmethod
    def build_embed(
        cls, record: Record, *, strategy: EmbedDataStrategy
    ) -> discord.Embed:
        return cls.build_embeds([record], strategy=strategy)[0]


class RankDetail(msgspec.Struct):
    difficulty: str
    completions: int
    gold: int
    silver: int
    bronze: int
    rank_met: bool
    gold_rank_met: bool
    silver_rank_met: bool
    bronze_rank_met: bool
