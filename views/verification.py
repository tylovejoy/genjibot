from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord

from utils import cache, constants, models, utils
from utils.newsfeed import NewsfeedEvent

if TYPE_CHECKING:
    import asyncpg

    import core
    import database


log = logging.getLogger(__name__)


class RejectReasonModal(discord.ui.Modal, title="Rejection Reason"):
    """Reject modal for reasoning."""

    reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.long)

    async def on_submit(self, itx: discord.Interaction[core.Genji]) -> None:
        """Reject modal submission callback."""
        await itx.response.send_message("Sending reason to user.", ephemeral=True)


class VerificationView(discord.ui.View):
    """Verification view for completions and records."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:accept",
    )
    async def green(self, itx: discord.Interaction[core.Genji], button: discord.ui.Button) -> None:
        """Accept button."""
        await itx.response.defer(ephemeral=True)
        await self.verification(itx, True)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.red,
        custom_id="persistent_view:reject",
    )
    async def red(self, itx: discord.Interaction[core.Genji], button: discord.ui.Button) -> None:
        """Reject button."""
        modal = RejectReasonModal()
        await itx.response.send_modal(modal)
        await modal.wait()
        await self.verification(itx, False, modal.reason.value)

    @staticmethod
    async def _fetch_record_by_hidden_id(db: database.Database, hidden_id: int) -> models.Record | None:
        query = """
            SELECT
                rq.*, m.official
            FROM records rq
            LEFT JOIN maps m on rq.map_code = m.map_code
            WHERE hidden_id=$1
        """
        rows = await db.fetchrow(query, hidden_id)
        if not rows:
            return None
        return models.Record(**rows)

    @staticmethod
    async def _fetch_medals(db: database.Database, map_code: str) -> asyncpg.Record:
        query = """
            SELECT
                coalesce(gold, 0),
                coalesce(silver, 0),
                coalesce(bronze, 0)
            FROM map_medals mm RIGHT JOIN maps m ON m.map_code = mm.map_code
            WHERE m.map_code = 'EF3CT';
        """
        row = await db.fetchrow(query, map_code)
        if not row:
            raise ValueError("Record not found.")
        for key in row:
            row["key"] = float(key)
        return await db.fetchrow(query, map_code)

    @staticmethod
    async def _verify_record(db: database.Database, hidden_id: int, verifier_id: int) -> None:
        query = """
            UPDATE records SET verified=True, verified_by=$2 WHERE hidden_id=$1
        """
        await db.execute(query, hidden_id, verifier_id)

    @staticmethod
    async def _verify_quality_rating(db: database.Database, map_code: str, user_id: int) -> None:
        query = "UPDATE map_ratings SET verified=True WHERE map_code=$1 AND user_id=$2"
        await db.execute(query, map_code, user_id)

    @staticmethod
    async def _get_record_for_newsfeed(db: database.Database, user_id: int, map_code: str) -> asyncpg.Record:
        query = """
            WITH map AS (
                SELECT
                    m.map_code,
                    m.map_name,
                    string_agg(distinct (nickname), ', ') as creators
                FROM maps m
                LEFT JOIN map_creators mc on m.map_code = mc.map_code
                LEFT JOIN users u on mc.user_id = u.user_id
                GROUP BY m.map_code, m.map_name),
            ranks AS (
                SELECT
                    u.nickname,
                    r.user_id,
                    record,
                    screenshot,
                    video,
                    verified,
                    r.map_code,
                    map.map_name,
                    map.creators,
                    rank() OVER (
                        PARTITION BY r.map_code, r.user_id
                        ORDER BY inserted_at DESC
                    ) AS latest
                FROM records r
                LEFT JOIN users u on r.user_id = u.user_id
                LEFT JOIN map on map.map_code = r.map_code
                WHERE map.map_code = $1
            )
            SELECT
                user_id,
                map_name,
                creators,
                map_code,
                record,
                video,
                nickname,
                screenshot,
                RANK() OVER (
                    ORDER BY record
                ) rank_num
            FROM ranks
            WHERE user_id = $2 AND latest = 1 AND verified
        """
        return await db.fetchrow(query, map_code, user_id)

    async def verification(
        self,
        itx: discord.Interaction[core.Genji],
        verified: bool,
        rejection: str | None = None,
    ) -> None:
        """Verify a record."""
        search = await self._fetch_record_by_hidden_id(itx.client.database, itx.message.id)
        if not search:
            raise ValueError
        if search.user_id == itx.user.id:
            await itx.followup.send(content="You cannot verify your own submissions.")
            return
        self.stop()
        original_message = await self.find_original_message(itx, search.channel_id, search.message_id)
        if not original_message:
            return
        record_submitter = itx.guild.get_member(search.user_id)

        if verified:
            medals = await self._fetch_medals(itx.client.database, search.map_code)

            data = self.accepted(itx.user.mention, search)
            await self._verify_record(itx.client.database, itx.message.id, itx.user.id)
            await self._verify_quality_rating(itx.client.database, search.map_code, record_submitter.id)
            if search.official:
                await utils.auto_skill_role(itx.client, itx.guild, record_submitter)

            newsfeed_data = await self._get_record_for_newsfeed(
                itx.client.database, record_submitter.id, search.map_code
            )
            if (
                newsfeed_data
                and search.video
                and search.icon_generator not in [constants.PARTIAL_VERIFIED, constants.FULLY_VERIFIED]
            ):
                _data = {
                    "map": {
                        "map_code": newsfeed_data["map_code"],
                        "map_name": newsfeed_data["map_name"],
                        "creators": newsfeed_data["creators"],
                        "gold": medals["gold"],
                        "silver": medals["silver"],
                        "bronze": medals["bronze"],
                    },
                    "record": {
                        "record": float(newsfeed_data["record"]),
                        "video": newsfeed_data["video"],
                        "rank_num": newsfeed_data["rank_num"],
                    },
                    "user": {
                        "user_id": newsfeed_data["user_id"],
                        "nickname": newsfeed_data["nickname"],
                    },
                }
                event = NewsfeedEvent("record", _data)
                await itx.client.genji_dispatch.handle_event(event, itx.client)

        else:
            data = self.rejected(itx.user.mention, search, rejection)

        await original_message.edit(content=data["edit"])
        flags = await itx.client.database.fetch_user_flags(record_submitter.id)
        flags = cache.SettingFlags(flags)
        with contextlib.suppress(discord.NotFound, discord.Forbidden):
            if cache.SettingFlags.VERIFICATION in flags:
                await record_submitter.send(f"`{'- ' * 14}`\n{data['direct_message']}\n`{'- ' * 14}`")
        await itx.message.delete()

    @staticmethod
    async def find_original_message(
        itx: discord.Interaction[core.Genji], channel_id: int, message_id: int
    ) -> discord.Message | None:
        """Try to fetch message from either Records channel."""
        try:
            res = await itx.guild.get_channel(channel_id).fetch_message(message_id)
        except (discord.NotFound, discord.HTTPException):
            res = None
        return res

    @staticmethod
    def accepted(
        verifier_mention: str,
        search: models.Record,
    ) -> dict[str, str]:
        """Get data for verified records."""
        if search.completion:
            search.record = "Completion"

        icon = search.icon_generator
        record = f"**Record:** {search.record} " f"{icon}"
        if search.video:
            edit = f"{icon} Complete verification by {verifier_mention}!"
        else:
            edit = f"{icon} Partial verification by {verifier_mention}! " f"No video proof supplied."
        return {
            "edit": edit,
            "direct_message": (
                f"**Map Code:** {search.map_code}\n" + record + f"verified by {verifier_mention}!\n\n" + ALERT
            ),
        }

    @staticmethod
    def rejected(
        verifier_mention: str,
        search: models.Record,
        rejection: str,
    ) -> dict[str, str]:
        """Get data for rejected records."""
        if search.completion:
            search.record = "Completion"

        record = f"**Record:** {search.record}\n"

        return {
            "edit": f"{constants.UNVERIFIED} " f"Rejected by {verifier_mention}!",
            "direct_message": (
                f"**Map Code:** {search.map_code}\n" + record + f"Your record got {constants.UNVERIFIED} "
                f"rejected by {verifier_mention}!\n\n"
                f"**Reason:** {rejection}\n\n" + ALERT
            ),
        }


ALERT = (
    # "Don't like these alerts? "
    # "Turn it off by using the command `/alerts false`.\n"
    "You can change your display name " "for records in the bot with the command `/name`!"
)
