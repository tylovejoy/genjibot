import asyncio
import contextlib
import logging
import os

import aiohttp
import discord

import core
import database


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


async def main() -> None:
    """Start the bot instance."""
    async with (
        aiohttp.ClientSession() as session,
        database.DatabaseConnection(
            f"postgres://postgres:{os.environ['PSQL_PASSWORD']}@{os.environ['PSQL_HOST']}/genji"
        ) as connection,
    ):
        bot = core.Genji(session=session, db=database.Database(connection))
        async with bot:
            with contextlib.suppress(discord.errors.ConnectionClosed):
                await bot.start(os.environ["TOKEN"])


if __name__ == "__main__":
    with setup_logging():
        asyncio.run(main())
