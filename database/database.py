import logging
import textwrap
import typing
from io import BytesIO

import asyncpg

import utils


class DatabaseConnection:
    """Handles asyncronous context manager for database connection."""

    def __init__(self, dsn: str):
        self.connection: asyncpg.Pool | None = None
        self.dsn = dsn

    async def __aenter__(self):
        self.connection = await asyncpg.create_pool(self.dsn)
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection.close()


class DotRecord(asyncpg.Record):
    """Adds dot access to asyncpg.Record."""

    def __getattr__(self, attr: str):
        return super().__getitem__(attr)

    def __hash__(self):
        return hash(self.values())


class Database:
    """Handles all database transactions."""

    def __init__(self, conn: asyncpg.Pool):
        self.logger: logging.Logger | None = None
        self.pool = conn

    async def copy_from_query(self, query):
        async with self.pool.acquire() as conn:
            buf = BytesIO()
            await conn.copy_from_query(
                query,
                output=buf,
                format="csv",
                header=True,
            )
            buf.seek(0)
            return buf

    async def get(
        self,
        query: str,
        *args: typing.Any,
    ) -> typing.Generator[None, None, DotRecord]:
        """
        The get_query_handler function is a helper function
        that takes in a model and query string.
        It then returns the results of the query as an array of records.
        Args:
            query (str) Specify the query that will be executed
            *args (Any) Pass in any additional arguments that are
                needed to be passed into the query
        Yields:
            DotRecords
        """
        if self.pool is None:
            raise utils.DatabaseConnectionError()
        query = textwrap.dedent(query)
        self.logger.debug(query)
        self.logger.debug(args)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                async for record in conn.cursor(
                    query,
                    *args,
                    record_class=DotRecord,
                ):
                    yield record

    async def get_row(self, query: str, *args: typing.Any) -> DotRecord | None:
        res = [x async for x in self.get(query, *args)]
        if res:
            res = res[0]
        return res

    async def set(
        self,
        query: str,
        *args: typing.Any,
    ):
        """
        The set_query_handler function takes a query string
        and an arbitrary number of arguments.
        It then executes the given query with the given arguments.
        Used for INSERT queries.
        Args:
            query (str) Store the query string
            *args (Any) Pass any additional arguments to the query
        """
        if self.pool is None:
            raise utils.DatabaseConnectionError()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(query, *args)

    async def set_many(
        self,
        query: str,
        *args: typing.Any,
    ):
        """
        The set_query_handler function takes a query string
        and an arbitrary number of arguments.
        It then executes the given query with the given arguments.
        Used for INSERT queries.
        Args:
            query (str) Store the query string
            *args (Any) Pass any additional arguments to the query
        """
        if self.pool is None:
            raise utils.DatabaseConnectionError()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(query, *args)
