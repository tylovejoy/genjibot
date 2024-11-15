from __future__ import annotations

import typing

import discord

if typing.TYPE_CHECKING:
    import core


async def add_remove_roles(itx: discord.Interaction[core.Genji], role) -> bool:
    if role in itx.user.roles:
        await itx.user.remove_roles(role)
        return False
    else:
        await itx.user.add_roles(role)
        return True


async def execute_button(itx: discord.Interaction[core.Genji], role_id: int):
    await itx.response.defer(ephemeral=True)
    role = itx.guild.get_role(role_id)
    res = await add_remove_roles(itx, role)
    await itx.followup.send(f"{role.name} {'added' if res else 'removed'}", ephemeral=True)


class AnnouncementRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="General Announcements",
        style=discord.ButtonStyle.grey,
        custom_id="gen_announce_role",
        row=0,
    )
    async def gen_announce_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1073292414271356938)

    @discord.ui.button(
        label="Patch Notes Announcements",
        style=discord.ButtonStyle.grey,
        custom_id="patch_announce_role",
        row=0,
    )
    async def patch_announce_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1073292274877878314)


class RegionRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="North America",
        style=discord.ButtonStyle.grey,
        custom_id="na_role",
        row=0,
    )
    async def na_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072934825981386893)

    @discord.ui.button(
        label="Europe",
        style=discord.ButtonStyle.grey,
        custom_id="eu_role",
        row=0,
    )
    async def eu_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072934890032615445)

    @discord.ui.button(
        label="Asia",
        style=discord.ButtonStyle.grey,
        custom_id="asia_role",
        row=0,
    )
    async def asia_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072934956227100803)

    # @discord.ui.button(
    #     label="CHINA",
    #     style=discord.ButtonStyle.grey,
    #     custom_id="china_role",
    # )
    # async def china_role(
    #         self, itx: discord.Interaction[core.Genji], button: discord.Button
    # ):
    #     await execute_button(itx, 1072935001206829148)

    @discord.ui.button(
        label="Oceana",
        style=discord.ButtonStyle.grey,
        custom_id="oce_role",
        row=1,
    )
    async def oce_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1073285809505046699)

    @discord.ui.button(
        label="South America",
        style=discord.ButtonStyle.grey,
        custom_id="sa_role",
        row=1,
    )
    async def sa_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1073285860239360060)

    @discord.ui.button(
        label="Africa",
        style=discord.ButtonStyle.grey,
        custom_id="africa_role",
        row=1,
    )
    async def africa_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1073285906422845600)


class ConsoleRoles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Console",
        emoji="🎮",
        style=discord.ButtonStyle.grey,
        custom_id="console_role",
    )
    async def console_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072935043766427718)

    @discord.ui.button(
        label="PC",
        emoji="⌨",
        style=discord.ButtonStyle.grey,
        custom_id="pc_role",
    )
    async def pc_role(self, itx: discord.Interaction[core.Genji], button: discord.Button):
        await execute_button(itx, 1072935061202141204)
