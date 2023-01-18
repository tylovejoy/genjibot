from __future__ import annotations

import typing

import discord

if typing.TYPE_CHECKING:
    import core


async def add_remove_roles(itx: core.Interaction[core.Genji], role):
    if role in itx.user.roles:
        await itx.user.remove_roles(role)
    else:
        await itx.user.add_roles(role)


# TODO: Change these roles
class RegionRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="NA",
        style=discord.ButtonStyle.blurple,
        custom_id="na_role",
    )
    async def na_role(self, itx: core.Interaction[core.Genji], button: discord.Button):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(1034572821139050567)
        await add_remove_roles(itx, role)

    @discord.ui.button(
        label="EU",
        style=discord.ButtonStyle.blurple,
        custom_id="eu_role",
    )
    async def eu_role(self, itx: core.Interaction[core.Genji], button: discord.Button):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(1054431520170971287)
        await add_remove_roles(itx, role)

    @discord.ui.button(
        label="ASIA",
        style=discord.ButtonStyle.blurple,
        custom_id="asia_role",
    )
    async def asia_role(
        self, itx: core.Interaction[core.Genji], button: discord.Button
    ):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(1054431532598702170)
        await add_remove_roles(itx, role)

    @discord.ui.button(
        label="CHINA",
        style=discord.ButtonStyle.blurple,
        custom_id="china_role",
    )
    async def china_role(
        self, itx: core.Interaction[core.Genji], button: discord.Button
    ):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(1054431547257790524)
        await add_remove_roles(itx, role)


class ConsoleRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Console",
        emoji="🎮",
        style=discord.ButtonStyle.blurple,
        custom_id="console_role",
    )
    async def console_role(
        self, itx: core.Interaction[core.Genji], button: discord.Button
    ):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(1060611275916324874)
        await add_remove_roles(itx, role)

    @discord.ui.button(
        label="PC",
        emoji="⌨",
        style=discord.ButtonStyle.blurple,
        custom_id="pc_role",
    )
    async def pc_role(self, itx: core.Interaction[core.Genji], button: discord.Button):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(1060611282883063919)
        await add_remove_roles(itx, role)
