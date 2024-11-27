import datetime
import json
from abc import ABC, abstractmethod

import asyncpg
import discord
import msgspec

import core
import database
from utils import constants, embeds, models, ranks
from utils.maps import DIFF_TO_RANK, MAP_DATA


class NewsfeedRecordResponse(msgspec.Struct):
    record: float | None = None
    video: str | None = None


class NewsfeedUserResponse(msgspec.Struct):
    user_id: int | None = None
    nickname: str | None = None
    roles: list[str] | None = None


class NewsfeedMapResponse(msgspec.Struct):
    map_name: str | None = None
    map_type: list[str] | None = None
    map_code: str | None = None
    desc: str | None = None
    official: bool | None = None
    archived: bool | None = None
    guide: list[str] | None = None
    mechanics: list[str] | None = None
    restrictions: list[str] | None = None
    checkpoints: int | None = None
    creators: list[str] | None = None
    difficulty: str | None = None
    quality: float | None = None
    creator_ids: list[int] | None = None
    gold: float | None = None
    silver: float | None = None
    bronze: float | None = None

class NewsfeedDataResponse(msgspec.Struct):
    map: NewsfeedMapResponse | None = None
    user: NewsfeedUserResponse | None = None
    record: NewsfeedRecordResponse | None = None

class NewsfeedResponse(msgspec.Struct):
    type: str
    timestamp: datetime.datetime
    data: NewsfeedDataResponse

def parse_newsfeed_data(data: dict) -> NewsfeedResponse:


    user_data = NewsfeedUserResponse(**data.get("user", {})) if "user" in data else None
    map_data = NewsfeedMapResponse(**data.get("map", {})) if "map" in data else None
    record_data = NewsfeedRecordResponse(**data.get("record", {})) if "record" in data else None

    _data = NewsfeedDataResponse(map=map_data, user=user_data, record=record_data)
    msgspec.json.encode(_data)
    return _data
    return NewsfeedResponse(type=type_, timestamp=timestamp, data=_data)

class NewsfeedEvent:
    def __init__(self, event_type: str, data: dict) -> None:
        self.event_type: str = event_type
        self.data: dict = data


class EmbedBuilder(ABC):
    event_type: str

    @abstractmethod
    def build(self, data: NewsfeedResponse) -> discord.Embed:
        """Build a list of embeds based on the event data."""
        raise NotImplementedError


class EventHandler:

    def __init__(self) -> None:
        self._registry = {}
        self._register_handlers()

    def register_handler(self, event_type: str, builder: EmbedBuilder) -> None:
        """Register an embed builder for a specific event type."""
        self._registry[event_type] = builder

    def _register_handlers(self) -> None:
        """Automatically discovers and registers all EmbedBuilder subclasses."""
        for cls in EmbedBuilder.__subclasses__():
            # Use the `event_type` attribute in the subclass to register it
            if hasattr(cls, "event_type"):
                self.register_handler(cls.event_type, cls())
            else:
                raise ValueError(f"EmbedBuilder subclass {cls.__name__} is missing the 'event_type' attribute.")

    async def handle_event(self, event: NewsfeedEvent, bot: core.Genji) -> None:
        """Handle an incoming event and posts to the specified channel."""
        builder = self._registry.get(event.event_type)
        if not builder:
            raise ValueError(f"No handler registered for event type: {event.event_type}")

        embed = builder.build(event.data)
        channel = bot.get_channel(constants.NEWSFEED)
        assert isinstance(channel, discord.TextChannel)
        await channel.send(embed=embed)
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
        json_data = json.dumps(event.data)
        await bot.database.execute(query, event.event_type, json_data)


class RecordEmbedBuilder(EmbedBuilder):
    event_type = "record"
    def build(self, data: dict) -> discord.Embed:
        record = models.Record(**data["map"], **data["user"], **data["record"])

        embed = embeds.GenjiEmbed(
            url=record.screenshot,
            description=(
                f"**{record.map_name} by {record.creators} ({record.map_code})**\n"
                f"┣ `Record` {record.record} {record.icon_generator}\n"
                f"┗ `Video` [Link]({record.video})"
            ),
            color=discord.Color.yellow(),
        )

        if record.rank_num == 1:
            embed.title = f"{record.nickname} set a new World Record!"
        else:
            embed.title = f"{record.nickname} got a medal!"
        return embed


class NewMapEmbedBuilder(EmbedBuilder):
    event_type = "new_map"
    def build(self, data: dict) -> discord.Embed:
        nickname = data["user"]["nickname"]
        difficulty = data["map"]["difficulty"]
        map_name = data["map"]["map_name"]
        map_code = data["map"]["map_code"]
        embed = embeds.GenjiEmbed(
            title=f"{nickname} has submitted a new {difficulty} map on {map_name}!\n",
            description=f"Use the command `/map-search map_code:{map_code}` to see the details!",
            color=getattr(
                MAP_DATA.get(map_name, discord.Color.from_str("#000000")),
                "COLOR",
                discord.Color.from_str("#000000"),
            ),
        )
        embed.set_image(url=getattr(MAP_DATA.get(map_name, None), "IMAGE_URL", None))
        base_thumbnail_url = "https://bkan0n.com/assets/images/genji_ranks/"
        rank = DIFF_TO_RANK[difficulty.replace("+", "").replace("-", "").rstrip()].lower()
        embed.set_thumbnail(url=f"{base_thumbnail_url}{rank}.png")

        return embed

class _ArchivalExtra:
    event_type: str

    def prepare_embed(self, data: dict, description: str) -> discord.Embed:
        map_code = data["map"]["map_code"]
        creators = data["map"]["creators"]
        map_name = data["map"]["map_name"]
        difficulty = data["map"]["difficulty"]

        embed = embeds.GenjiEmbed(
            title=f"{map_code} has been {self.event_type}d.",
            description=description,
            color=discord.Color.red(),
        )

        embed.add_description_field(
            name=f"{map_code}",
            value=(
                f"`Creator` {discord.utils.escape_markdown(creators)}\n"
                f"`Map` {map_name}\n"
                f"`Difficulty` {ranks.convert_num_to_difficulty(difficulty)}\n"
            ),
        )
        return embed

class ArchivedMapEmbedBuilder(EmbedBuilder, _ArchivalExtra):
    event_type = "archive"
    def build(self, data: dict) -> discord.Embed:
        description = (
            "This map will not appear in the map search command unless searched by map code.\n"
            "You cannot submit records for archived maps."
        )
        return self.prepare_embed(data, description)


class UnarchivedMapEmbedBuilder(EmbedBuilder, _ArchivalExtra):
    event_type = "unarchive"
    def build(self, data: dict) -> discord.Embed:
        description = "This map will now appear in the map search command and be eligible for record submissions."
        return self.prepare_embed(data, description)
