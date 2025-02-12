from __future__ import annotations

import asyncio
import logging
import typing

import discord
from discord.ext import commands

import cogs
from utils.newsfeed import EventHandler
from utils.notifications import NotificationService
from utils.rabbit.client import Rabbit

if typing.TYPE_CHECKING:
    import datetime

    import aiohttp
    import arsenic

    import database
    from utils.xp import XPManager
    from views import PlaytestVoting

log = logging.getLogger(__name__)


class Genji(commands.Bot):
    """Genji bot class inherited from commands.Bot."""

    database: database.Database
    rabbit: Rabbit
    firefox: arsenic.Session
    xp_enabled: bool
    xp_manager: XPManager
    notification_manager: NotificationService

    def __init__(self, *, session: aiohttp.ClientSession) -> None:
        super().__init__(
            "?",
            intents=self._generate_intents(),
            help_command=None,
        )
        self.session = session
        self.playtest_views: dict[int, PlaytestVoting] = {}
        self.persistent_views_added = False
        self.analytics_buffer: list[tuple[str, int, datetime.datetime, dict]] = []
        self.genji_dispatch = EventHandler()
        self.xp_enabled = True
        self.notification_manager = NotificationService(self)

    def log_analytics(self, event: str, user_id: int, timestamp: datetime.datetime, data: dict) -> None:
        self.analytics_buffer.append((event, user_id, timestamp, data))

    async def _prepare_rabbitmq(self) -> None:
        await self.wait_until_ready()
        self.rabbit = Rabbit(self)

    async def setup_hook(self) -> None:
        """Execute code during setup.

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
        for ext in [*cogs.EXTENSIONS, "jishaku", "core.events"]:
            log.info(f"Loading {ext}...")
            await self.load_extension(ext)

        self.rabbitmq_task = asyncio.create_task(self._prepare_rabbitmq())

    @staticmethod
    def _generate_intents() -> discord.Intents:
        """Generate intents.

        The _generate_intents function generates the intents for the bot.
        This is used to generate a discord.Intents object that can be passed into
        the Bot constructor as an argument.

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
        )
        return intents
