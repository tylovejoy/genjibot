from __future__ import annotations

import datetime
import logging
import typing

import discord
from discord.ext import commands

import cogs
import core
import utils
from views import PlaytestVoting

if typing.TYPE_CHECKING:
    import aiohttp

    import database


class Genji(commands.Bot):
    """Genji bot class inherited from commands.Bot."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        db: database.Database,
    ) -> None:
        super().__init__(
            "?",
            intents=self._generate_intents(),
            help_command=None,
        )
        self.session = session
        self.database = db
        self.logger = self._setup_logging()
        self.database.logger = self.logger
        self.cache: utils.GenjiCache = utils.GenjiCache()
        self.playtest_views: dict[int, PlaytestVoting] = {}
        self.persistent_views_added = False
        self.analytics_buffer: list[tuple[str, int, datetime.datetime, dict]] = []

    def log_analytics(
        self, event: str, user_id: int, timestamp: datetime.datetime, data: dict
    ):
        self.analytics_buffer.append((event, user_id, timestamp, data))

    async def setup_hook(self) -> None:
        """
        The setup_hook function is called when the bot is starting up.
        It's responsible for loading all the cogs that are in
        the initial_extensions list. This function is also used
        to start a connection with the database,
        and register any tasks that need to be run on a loop.

        Args:
            self: bot instance

        Returns:
            None
        """

        for ext in cogs.EXTENSIONS + ["jishaku", "core.events"]:
            self.logger.info(f"Loading {ext}...")
            await self.load_extension(ext)

    @staticmethod
    def _setup_logging() -> logging.Logger:
        """
        The _setup_logging function sets up the logging module for use with Discord.
        It sets the log level to INFO and creates a StreamHandler that prints to stdout.
        The formatter is set to display the name of the logger,
        its level, and its message.

        Returns:
            The logger object
        """
        logger = logging.getLogger("discord")
        logger.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "{asctime} | {levelname: <8} | "
                "{module}:{funcName}:{lineno} - {message}",
                style="{",
            )
        )
        logger.addHandler(console_handler)
        return logger

    @staticmethod
    def _generate_intents() -> discord.Intents:
        """
        The _generate_intents function generates the intents for the bot.
        This is used to generate a discord.Intents object that can be passed into
        the Bot constructor as an argument.

        Args:

        Returns:
            Intents
        """
        intents = discord.Intents(
            guild_messages=True,
            guilds=True,
            integrations=True,
            dm_messages=True,
            webhooks=True,
            members=True,
            message_content=True,
            guild_reactions=True,
            # invites=True,
            # emojis=True,
            # bans=True,
            # presences=True,
            # dm_typing=True,
            # voice_states=True,
            # dm_reactions=True,
            # guild_typing=True,
        )
        return intents

    async def on_command_error(self, context, exception):
        ...
