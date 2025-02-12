import asyncio
import contextlib
import logging
import os

import aiohttp
import discord
import sentry_sdk

import core
import database
from utils.xp import XPManager

SENTRY_TOKEN = os.getenv("SENTRY_TOKEN")
sentry_sdk.init(
    SENTRY_TOKEN,
    enable_tracing=True,
)


class RemoveNoise(logging.Filter):
    def __init__(self) -> None:
        super().__init__(name="discord.state")

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.levelname == "WARNING" and "referencing an unknown" in record.msg)


class RemoveShardCloseNoise(logging.Filter):
    def __init__(self) -> None:
        super().__init__(name="discord.client")

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.exc_info and discord.errors.ConnectionClosed in record.exc_info)


@contextlib.contextmanager
def setup_logging() -> None:
    """Set up logging."""
    log = logging.getLogger()

    try:
        discord.utils.setup_logging()
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("discord.state").addFilter(RemoveNoise())
        logging.getLogger("discord.client").addFilter(RemoveShardCloseNoise())
        log.setLevel(logging.INFO)
        yield
    finally:
        handlers = log.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr)


rabbitmq_user = os.getenv("RABBITMQ_DEFAULT_USER")
rabbitmq_pass = os.getenv("RABBITMQ_DEFAULT_PASS")


async def main() -> None:
    """Start the bot instance."""
    psql_dsn = f"postgres://postgres:{os.environ['PSQL_PASSWORD']}@genji-postgres/genji"
    logging.getLogger("discord.gateway").setLevel("WARNING")
    async with (
        aiohttp.ClientSession() as http_session,
        database.DatabaseConnection(psql_dsn) as psql_connection,
    ):
        bot = core.Genji(session=http_session)

        assert psql_connection
        bot.database = database.Database(psql_connection)
        bot.xp_manager = XPManager(bot)

        async with bot:
            with contextlib.suppress(discord.errors.ConnectionClosed):
                await bot.start(os.environ["TOKEN"])


if __name__ == "__main__":
    with setup_logging():
        asyncio.run(main())
