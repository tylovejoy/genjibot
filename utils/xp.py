from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Literal

import discord
from discord import Member

from utils.constants import GUILD_ID, Notification

if TYPE_CHECKING:
    import asyncpg

    from core import Genji
    from database import Database


log = logging.getLogger(__name__)


XP_TYPES = Literal["Map Submission", "Playtest", "Guide", "Completion", "Record", "World Record"]

XP_AMOUNTS: dict[XP_TYPES, int] = {
    "Map Submission": 30,
    "Playtest": 35,
    "Guide": 35,
    "Completion": 5,
    "Record": 15,
    "World Record": 50,
}

GENJI_API_KEY: str = os.getenv("GENJI_API_KEY", "")


class XPManager:
    def __init__(self, bot: Genji) -> None:
        self._bot: Genji = bot
        self._db: Database = bot.database

    async def set_active_key(self, key_type: str) -> None:
        resp = await self._bot.session.put(
            f"https://api.genji.pk/v1/lootbox/keys/{key_type}", headers={"X-API-KEY": GENJI_API_KEY}
        )
        if not resp.ok:
            raise ValueError

    async def grant_active_key(self, user_id: int) -> None:
        key_type = await self._db.fetchval("SELECT key FROM lootbox_active_key;")
        await self._bot.session.post(
            f"https://api.genji.pk/v1/lootbox/user/{user_id}/keys/{key_type}", headers={"X-API-KEY": GENJI_API_KEY}
        )

    async def grant_key(self, user_id: int, key_type: str) -> None:
        await self._bot.session.post(
            f"https://api.genji.pk/v1/lootbox/user/{user_id}/keys/{key_type}", headers={"X-API-KEY": GENJI_API_KEY}
        )

    async def _xp_notification(self, result: asyncpg.Record, user_id: int, amount: int, type_: str) -> None:
        if result is None:
            raise ValueError

        guild = self._bot.get_guild(GUILD_ID)
        assert guild
        xp_channel = guild.get_channel(1324496532447166505)
        assert isinstance(xp_channel, discord.TextChannel)
        user = guild.get_member(user_id)
        assert user

        await self._bot.notification_manager.notify_channel_default_to_no_ping(
            xp_channel,
            user_id,
            Notification.PING_ON_XP_GAIN,
            f"<:_:976917981009440798> {user.display_name} has gained **{amount} XP** ({type_})!"
        )

        _xp_data = await self._check_xp_tier_change(result["previous_amount"], result["new_amount"])

        if _xp_data is None:
            raise ValueError

        if _xp_data["rank_change_type"]:
            old_rank = " ".join((_xp_data["old_main_tier_name"], _xp_data["old_sub_tier_name"]))
            new_rank = " ".join((_xp_data["new_main_tier_name"], _xp_data["new_sub_tier_name"]))

            await self.grant_active_key(user_id)
            await self._update_xp_roles_for_user(
                guild,
                user_id,
                _xp_data["old_main_tier_name"],
                _xp_data["new_main_tier_name"],
            )

            await self._bot.notification_manager.notify_dm(
                user_id,
                Notification.DM_ON_LOOTBOX_GAIN,
                (
                    f"Congratulations! You have ranked up to **{new_rank}**!\n"
                    "[Log into the website to open your lootbox!](https://genji.pk/lootbox.php)"
                )
            )

            await self._bot.notification_manager.notify_channel_default_to_no_ping(
                xp_channel,
                user_id,
                Notification.PING_ON_COMMUNITY_RANK_UPDATE,
                f"<:_:976468395505614858> {user.display_name} has ranked up! **{old_rank}** -> **{new_rank}**\n"
            )


        if _xp_data["prestige_change"]:
            for _ in range(15):
                await self.grant_active_key(user_id)

            old_rank = " ".join((_xp_data["old_main_tier_name"], _xp_data["old_sub_tier_name"]))
            new_rank = " ".join((_xp_data["new_main_tier_name"], _xp_data["new_sub_tier_name"]))

            await self._update_xp_roles_for_user(
                guild,
                user_id,
                _xp_data["old_main_tier_name"],
                _xp_data["new_main_tier_name"],
            )

            await self._update_xp_prestige_roles_for_user(
                guild,
                user_id,
                _xp_data["old_prestige_level"],
                _xp_data["new_prestige_level"],
            )

            await self._bot.notification_manager.notify_dm(
                user_id,
                Notification.DM_ON_LOOTBOX_GAIN,
                (
                    f"Congratulations! You have prestiged up to **{_xp_data['new_prestige_level']}**!\n"
                    "[Log into the website to open your 15 lootboxes!](https://genji.pk/lootbox.php)"
                )
            )

            await self._bot.notification_manager.notify_channel_default_to_no_ping(
                xp_channel,
                user_id,
                Notification.PING_ON_COMMUNITY_RANK_UPDATE,
                (
                    f"<:_:976468395505614858><:_:976468395505614858><:_:976468395505614858>"
                    f" {user.display_name} has prestiged! "
                    f"**Prestige {_xp_data['old_prestige_level']}** -> **Prestige {_xp_data['new_prestige_level']}**"
                )
            )

    @staticmethod
    async def _update_xp_prestige_roles_for_user(
        guild: discord.Guild, user_id: int, old_prestige_level: int, new_prestige_level: int,
    ) -> None:
        old_prestige_role = discord.utils.get(guild.roles, name=f"Prestige {old_prestige_level}")
        new_prestige_role = discord.utils.get(guild.roles, name=f"Prestige {new_prestige_level}")
        if not (old_prestige_role or new_prestige_role):
            log.info(
                f"Old prestige level: {old_prestige_level}\n"
                "New prestige level: {new_prestige_level}\nUser ID: {user_id}"
            )
            raise ValueError("Can't update xp prestige roles for user.")
        assert old_prestige_role and new_prestige_role
        member = guild.get_member(user_id)
        assert member
        roles = set(member.roles)
        roles.discard(old_prestige_role)
        roles.add(new_prestige_role)
        await member.edit(roles=roles)

    @staticmethod
    async def _update_xp_roles_for_user(
        guild: discord.Guild, user_id: int, old_tier_name: str, new_tier_name: str
    ) -> None:
        old_rank = discord.utils.get(guild.roles, name=old_tier_name)
        new_rank = discord.utils.get(guild.roles, name=new_tier_name)
        if not (old_rank or new_rank):
            log.info(f"Old tier name: {old_tier_name}\nNew tier name: {new_tier_name}\nUser ID: {user_id}")
            raise ValueError("Can't update xp roles for user.")
        assert old_rank and new_rank
        member = guild.get_member(user_id)
        assert member
        roles = set(member.roles)
        roles.discard(old_rank)
        roles.add(new_rank)
        await member.edit(roles=roles)

    async def grant_user_xp_type(self, user_id: int, type_: XP_TYPES) -> None:
        result = await self._grant_xp(user_id, XP_AMOUNTS[type_])
        await self._xp_notification(result, user_id, XP_AMOUNTS[type_], type_)

    async def _grant_xp(self, user_id: int, amount: int) -> asyncpg.Record:
        query = """
            WITH old_values AS (
                SELECT amount
                FROM xptable
                WHERE user_id = $1
            ),
            upsert_result AS (
                INSERT INTO xptable (user_id, amount)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE
                SET amount = xptable.amount + EXCLUDED.amount
                RETURNING xptable.amount
            )
            SELECT
                COALESCE((SELECT amount FROM old_values), 0) AS previous_amount,
                (SELECT amount FROM upsert_result) AS new_amount;
        """
        return await self._db.fetchrow(query, user_id, amount)

    async def grant_user_xp_amount(self, user_id: int, amount: int, granted_by: Member, hidden: bool = True) -> None:
        result = await self._grant_xp(user_id, amount)
        if not hidden:
            await self._xp_notification(result, user_id, amount, f"Granted by {granted_by}")

    async def _xp_newsfeed(self, user_id: int) -> None: ...

    async def _check_xp_tier_change(self, old_xp: int, new_xp: int) -> asyncpg.Record:
        query = """
            WITH old_tier AS (
                SELECT
                    $1::int AS old_xp,
                    (($1 / 100) % 100) AS old_normalized_tier,
                    (($1 / 100) / 100) AS old_prestige_level,
                    x.name AS old_main_tier_name,
                    s.name AS old_sub_tier_name
                FROM _metadata_xp_tiers x
                LEFT JOIN _metadata_xp_sub_tiers s ON (($1 / 100) % 5) = s.threshold
                WHERE (($1 / 100) % 100) / 5 = x.threshold
            ),
            new_tier AS (
                SELECT
                    $2::int AS new_xp,
                    (($2 / 100) % 100) AS new_normalized_tier,
                    (($2 / 100) / 100) AS new_prestige_level,
                    x.name AS new_main_tier_name,
                    s.name AS new_sub_tier_name
                FROM _metadata_xp_tiers x
                LEFT JOIN _metadata_xp_sub_tiers s ON (($2 / 100) % 5) = s.threshold
                WHERE (($2 / 100) % 100) / 5 = x.threshold
            )
            SELECT
                o.old_xp,
                n.new_xp,
                o.old_main_tier_name,
                n.new_main_tier_name,
                o.old_sub_tier_name,
                n.new_sub_tier_name,
                old_prestige_level,
                new_prestige_level,
                CASE
                    WHEN o.old_main_tier_name != n.new_main_tier_name THEN 'Main Tier Rank Up'
                    WHEN o.old_sub_tier_name != n.new_sub_tier_name THEN 'Sub-Tier Rank Up'
                END AS rank_change_type,
                o.old_prestige_level != n.new_prestige_level AS prestige_change
            FROM old_tier o
            JOIN new_tier n ON TRUE;
        """
        return await self._db.fetchrow(query, old_xp, new_xp)
