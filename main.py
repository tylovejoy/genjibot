import asyncio
import contextlib
import json
import logging
import os

import aio_pika
import aiohttp
import arsenic
import discord
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from aio_pika.pool import Pool
from arsenic import services, browsers

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

rabbitmq_user = os.getenv("RABBITMQ_DEFAULT_USER")
rabbitmq_pass = os.getenv("RABBITMQ_DEFAULT_PASS")


async def main() -> None:
    """Start the bot instance."""
    service = services.Geckodriver(binary="/usr/src/app/geckodriver", log_file=os.devnull)
    browser = browsers.Firefox(**{"moz:firefoxOptions": {"args": ["-headless", "-log", "{'level': 'warning'}"]}})
    async with (
        aiohttp.ClientSession() as session,
        database.DatabaseConnection(
            f"postgres://postgres:{os.environ['PSQL_PASSWORD']}@{os.environ['PSQL_HOST']}/genji"
        ) as connection,
        arsenic.get_session(service, browser) as firefox_session,
    ):
        bot = core.Genji(session=session, db=database.Database(connection))
        bot.firefox = firefox_session

        async def get_mq_connection() -> AbstractRobustConnection:
            return await aio_pika.connect_robust(f"amqp://{rabbitmq_user}:{rabbitmq_pass}@genji-rabbit")

        connection_pool: Pool = Pool(get_mq_connection)

        async def get_mq_channel() -> aio_pika.Channel:
            async with connection_pool.acquire() as _conn:
                return await _conn.channel()

        mq_channel_pool: Pool = Pool(get_mq_channel)

        bot = core.Genji(session=session)
        assert connection
        bot.database = database.Database(connection)
        bot.mq_channel_pool = mq_channel_pool

        async with bot:
            with contextlib.suppress(discord.errors.ConnectionClosed):
                await bot.start(os.environ["TOKEN"])


if __name__ == "__main__":
    with setup_logging():
        asyncio.run(main())
