import asyncio
import contextlib
import logging
import os

import aiohttp
import discord

import core
import database

import sentry_sdk

sentry_sdk.init(
    dsn="https://2324f323c0618c17ef5aaae6ba250312@sentry.bkan0n.com/4",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
)


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name="discord.state")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == "WARNING" and "referencing an unknown" in record.msg:
            return False
        return True


class RemoveShardCloseNoise(logging.Filter):
    def __init__(self):
        super().__init__(name="discord.client")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info and discord.errors.ConnectionClosed in record.exc_info:
            return False
        return True


@contextlib.contextmanager
def setup_logging():
    log = logging.getLogger()

    try:
        discord.utils.setup_logging()
        # __enter__
        max_bytes = 32 * 1024 * 1024  # 32 MiB
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("discord.state").addFilter(RemoveNoise())
        logging.getLogger("discord.client").addFilter(RemoveShardCloseNoise())
        log.setLevel(logging.INFO)
        yield
    finally:
        # __exit__
        handlers = log.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr)


async def main() -> None:
    """The main function is the entry point of the program.
    It creates a bot instance and runs it.
    """
    async with aiohttp.ClientSession() as session:
        async with database.DatabaseConnection(
            f"postgres://postgres:{os.environ['PSQL_PASSWORD']}@{os.environ['PSQL_HOST']}/genji"
        ) as connection:
            bot = core.Genji(session=session, db=database.Database(connection))
            async with bot:
                with contextlib.suppress(discord.errors.ConnectionClosed):
                    await bot.start(os.environ["TOKEN"])


if __name__ == "__main__":
    with setup_logging():
        asyncio.run(main())
