from typing import Generic, TypeVar

import discord
from discord.ext import commands

BotT = TypeVar("BotT", bound=commands.Bot)


class Interaction(discord.Interaction, Generic[BotT]):
    client: BotT
