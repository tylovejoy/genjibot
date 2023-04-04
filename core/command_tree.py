from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

import discord
from discord import app_commands

if TYPE_CHECKING:
    from discord.abc import Snowflake

    AppCommandStore = Dict[str, app_commands.AppCommand]  # name: AppCommand


class GenjiCommandTree(app_commands.CommandTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._global_app_commands: AppCommandStore = {}
        # guild_id: AppCommandStore
        self._guild_app_commands: Dict[int, AppCommandStore] = {}

    def find_app_command_by_names(
        self,
        *qualified_name: str,
        guild: Optional[Union[Snowflake, int]] = None,
    ) -> Optional[app_commands.AppCommand]:
        commands = self._global_app_commands
        if guild:
            guild_id = guild if isinstance(guild, int) else guild.id
            guild_commands = self._guild_app_commands.get(guild_id, {})
            if not guild_commands and self.fallback_to_global:
                commands = self._global_app_commands
            else:
                commands = guild_commands

        return next(
            (
                cmd
                for cmd_name, cmd in commands.items()
                if any(name in qualified_name for name in cmd_name.split())
            ),
            None,
        )

    def get_app_command(
        self,
        value: Union[str, int],
        guild: Optional[Union[Snowflake, int]] = None,
    ) -> Optional[app_commands.AppCommand]:
        def search_dict(d: AppCommandStore) -> Optional[app_commands.AppCommand]:
            for cmd_name, cmd in d.items():
                if value == cmd_name or (str(value).isdigit() and int(value) == cmd.id):
                    return cmd
            return None

        if guild:
            guild_id = guild if isinstance(guild, int) else guild.id
            guild_commands = self._guild_app_commands.get(guild_id, {})
            return (
                search_dict(guild_commands)
                or search_dict(self._global_app_commands)
                if self.fallback_to_global
                else search_dict(guild_commands)
            )
        else:
            return search_dict(self._global_app_commands)

    @staticmethod
    def _unpack_app_commands(
        commands: List[app_commands.AppCommand],
    ) -> AppCommandStore:
        ret: AppCommandStore = {}

        def unpack_options(
            options: List[
                Union[
                    app_commands.AppCommand,
                    app_commands.AppCommandGroup,
                    app_commands.Argument,
                ]
            ]
        ):
            for option in options:
                if isinstance(option, app_commands.AppCommandGroup):
                    ret[option.qualified_name] = option  # type: ignore
                    unpack_options(option.options)  # type: ignore

        for command in commands:
            ret[command.name] = command
            unpack_options(command.options)  # type: ignore

        return ret

    async def _update_cache(
        self,
        commands: Optional[List[app_commands.AppCommand]] = None,
        guild: Optional[Union[Snowflake, int]] = None,
    ) -> None:
        # because we support both int and Snowflake
        # we need to convert it to a Snowflake like object if it's an int
        _guild: Optional[Snowflake] = None
        if guild is not None:
            _guild = discord.Object(guild) if isinstance(guild, int) else guild
        if _guild:
            self._guild_app_commands[_guild.id] = self._unpack_app_commands(commands)
        else:
            self._global_app_commands = self._unpack_app_commands(commands)

    async def fetch_command(
        self, command_id: int, /, *, guild: Optional[Snowflake] = None
    ) -> app_commands.AppCommand:
        res = await super().fetch_command(command_id, guild=guild)
        await self._update_cache([res], guild=guild)
        return res

    async def fetch_commands(
        self, *, guild: Optional[Snowflake] = None
    ) -> List[app_commands.AppCommand]:
        res = await super().fetch_commands(guild=guild)
        await self._update_cache(res, guild=guild)
        return res

    def clear_app_commands_cache(self, *, guild: Optional[Snowflake]) -> None:
        if guild:
            self._guild_app_commands.pop(guild.id, None)
        else:
            self._global_app_commands = {}

    def clear_commands(
        self,
        *,
        guild: Optional[Snowflake],
        type_: Optional[discord.AppCommandType] = None,
        clear_app_commands_cache: bool = True,
    ) -> None:
        super().clear_commands(guild=guild)
        if clear_app_commands_cache:
            self.clear_app_commands_cache(guild=guild)

    async def sync(
        self, *, guild: Optional[Snowflake] = None
    ) -> List[app_commands.AppCommand]:
        res = await super().sync(guild=guild)
        await self._update_cache(res, guild=guild)
        return res
