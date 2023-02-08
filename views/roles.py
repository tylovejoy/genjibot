from __future__ import annotations

import typing

import discord

if typing.TYPE_CHECKING:
    import core


async def add_remove_roles(itx: core.Interaction[core.Genji], role) -> bool:
    if role in itx.user.roles:
        await itx.user.remove_roles(role)
        return False
    else:
        await itx.user.add_roles(role)
        return True


async def execute_button(itx: core.Interaction[core.Genji], role_id: int):
    await itx.response.defer(ephemeral=True)
    role = itx.guild.get_role(role_id)
    res = await add_remove_roles(itx, role)
    await itx.followup.send(f"{role.name} {'added' if res else 'removed'}", ephemeral=True)


class RegionRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="NA",
        style=discord.ButtonStyle.blurple,
        custom_id="na_role",
    )
    async def na_role(self, itx: core.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072934825981386893)

    @discord.ui.button(
        label="EU",
        style=discord.ButtonStyle.blurple,
        custom_id="eu_role",
    )
    async def eu_role(self, itx: core.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072934890032615445)

    @discord.ui.button(
        label="ASIA",
        style=discord.ButtonStyle.blurple,
        custom_id="asia_role",
    )
    async def asia_role(
            self, itx: core.Interaction[core.Genji], button: discord.Button
    ):
        await execute_button(itx, 1072934956227100803)

    @discord.ui.button(
        label="CHINA",
        style=discord.ButtonStyle.blurple,
        custom_id="china_role",
    )
    async def china_role(
            self, itx: core.Interaction[core.Genji], button: discord.Button
    ):
        await execute_button(itx, 1072935001206829148)


class ConsoleRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="CONSOLE",
        emoji="🎮",
        style=discord.ButtonStyle.blurple,
        custom_id="console_role",
    )
    async def console_role(
            self, itx: core.Interaction[core.Genji], button: discord.Button
    ):
        await execute_button(itx, 1072935043766427718)

    @discord.ui.button(
        label="PC",
        emoji="⌨",
        style=discord.ButtonStyle.blurple,
        custom_id="pc_role",
    )
    async def pc_role(self, itx: core.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072935061202141204)
