import json
from abc import ABC, abstractmethod

import discord

import database
from utils import constants, embeds, models


class NewsfeedEvent:
    def __init__(self, event_type: str, data: dict) -> None:
        self.event_type: str = event_type
        self.data: dict = data


class EmbedBuilder(ABC):
    @abstractmethod
    def build(self, data: dict) -> discord.Embed:
        """Build a list of embeds based on the event data."""
        raise NotImplementedError


class EventHandler:
    def __init__(self) -> None:
        self.registry: dict[str, EmbedBuilder] = {
            "new_map": NewMapEmbedBuilder(),
            "record": RecordEmbedBuilder(),
        }

    def register_handler(self, event_type: str, builder: EmbedBuilder) -> None:
        """Register an embed builder for a specific event type."""
        self.registry[event_type] = builder

    async def handle_event(self, event: NewsfeedEvent, guild: discord.Guild, db: database.Database) -> None:
        """Handle an incoming event and posts to the specified channel."""
        builder = self.registry.get(event.event_type)
        if not builder:
            raise ValueError(f"No handler registered for event type: {event.event_type}")

        embed = builder.build(event.data)
        channel = guild.get_channel(constants.NEWSFEED)
        assert isinstance(channel, discord.TextChannel)
        await channel.send(embed=embed)
        query = "INSERT INTO newsfeed (type, data) VALUES ($1, $2);"
        json_data = json.dumps(event.data)
        await db.execute(query, event.event_type, json_data)


class RecordEmbedBuilder(EmbedBuilder):
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
    def build(self, data: dict) -> discord.Embed:
        map_details = data["map"]
        embed = discord.Embed(
            title="New Map Submitted!",
            description=f"🗺️ A new map, **{map_details['name']}**, has been submitted!",
        )
        embed.add_field(name="Creator", value=map_details["creator"], inline=True)
        embed.add_field(name="Difficulty", value=map_details["difficulty"], inline=True)
        embed.set_footer(text="Check it out now!")
        return embed
