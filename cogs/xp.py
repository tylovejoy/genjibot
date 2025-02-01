from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Interaction, Member, app_commands
from discord.ext import commands

from utils import constants, transformers

if TYPE_CHECKING:
    import core

    Itx = Interaction[core.Genji]


@app_commands.guilds(constants.GUILD_ID)
class XPCog(commands.GroupCog, group_name="xp"):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    @app_commands.command(name="grant")
    async def _command_grant_xp(
        self,
        itx: Itx,
        user: Member,
        amount: app_commands.Range[int, 1, 100],
        hidden: bool = True,
    ) -> None:
        """Grant user XP. Amount is capped at 100 XP. Hidden is true by default."""
        await itx.response.send_message(f"Granting user {user} {amount} XP.", ephemeral=True)
        await self.bot.xp_manager.grant_user_xp_amount(user.id, amount, itx.user, hidden)

    @app_commands.command(name="set-active-key")
    async def _command_set_active_key(
        self,
        itx: Itx,
        key_type: app_commands.Transform[str, transformers.KeyTypeTransformer],
    ) -> None:
        """Set active key type."""
        if itx.user.id != 141372217677053952:
            return await itx.response.send_message("You are not authorized to use this command.", ephemeral=True)
        await itx.response.send_message(f"Setting active key to {key_type}.", ephemeral=True)
        await self.bot.xp_manager.set_active_key(key_type)


async def setup(bot: core.Genji) -> None:
    """Add cog to bot."""
    await bot.add_cog(XPCog(bot))
