from __future__ import annotations

import contextlib
import logging
import os
from typing import TYPE_CHECKING

import discord

from utils import constants, models, utils
from utils.newsfeed import NewsfeedEvent

if TYPE_CHECKING:
    import asyncpg

    import core
    import database


log = logging.getLogger(__name__)


GENJI_API_KEY: str = os.getenv("GENJI_API_KEY", "")


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
        row = await db.fetchrow(query, hidden_id)
        if not row:
            return None
        model = models.Record(**row)
        query = """
            WITH latest_records AS (
                SELECT
                    rq.map_code,
                    rq.record,
                    rq.user_id,
                    rq.completion,
                    rq.hidden_id,
                    rank() OVER (
                        PARTITION BY rq.map_code, rq.user_id
                        ORDER BY rq.inserted_at DESC
                    ) AS latest
                FROM records rq
                LEFT JOIN maps m on rq.map_code = m.map_code
                WHERE rq.map_code = $2
            ), ranked_records AS (
                SELECT
                    *,
                    RANK() OVER (PARTITION BY map_code ORDER BY completion, record) as rank_num
                FROM latest_records
                WHERE latest = 1
            )
            SELECT CASE WHEN completion THEN NULL ELSE rank_num END FROM ranked_records
            WHERE hidden_id = $1
        """
        model.rank_num = await db.fetchval(query, hidden_id, model.map_code)
        return model

    @staticmethod
    async def _fetch_medals(db: database.Database, map_code: str) -> asyncpg.Record:
        query = """
            SELECT
                coalesce(gold, 0),
                coalesce(silver, 0),
                coalesce(bronze, 0)
            FROM map_medals mm RIGHT JOIN maps m ON m.map_code = mm.map_code
            WHERE m.map_code = $1;
        """
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
                WHERE map.map_code = $1 AND legacy IS FALSE
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

            icon = search.icon_generator

            if newsfeed_data and search.video and icon not in [constants.PARTIAL_VERIFIED, constants.FULLY_VERIFIED]:
                _data = {
                    "map": {
                        "map_code": newsfeed_data["map_code"],
                        "map_name": newsfeed_data["map_name"],
                        "creators": newsfeed_data["creators"],
                        "gold": medals.get("gold"),
                        "silver": medals.get("silver"),
                        "bronze": medals.get("bronze"),
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

            if itx.client.xp_enabled or search.user_id in [141372217677053952, 681391478605479948]:
                try:
                    await self._process_map_mastery(itx, search)
                except Exception as e:
                    log.info("Process Map Mastery Failed")
                    log.info(f"Error: {e}", exc_info=True)
                    log.info("-----------------------------")

                if icon in ["", constants.PARTIAL_VERIFIED]:  # Completion
                    log.debug("<- Completion %s %s", search.user_id, search.map_code)
                    query = "SELECT count(*) FROM records WHERE user_id = $1 AND map_code = $2 AND verified;"
                    count = await itx.client.database.fetchval(query, search.user_id, search.map_code)
                    log.debug(f"Completion: {count} %s %s", search.user_id, search.map_code)
                    if count == 1:
                        await itx.client.xp_manager.grant_user_xp_type(search.user_id, "Completion")
                        log.debug("Completion: granted XP. %s %s", search.user_id, search.map_code)
                elif icon in [constants.NON_MEDAL_WR, constants.GOLD_WR, constants.SILVER_WR, constants.BRONZE_WR]:
                    log.info("<- WR %s %s", search.user_id, search.map_code)
                    query = """
                        SELECT EXISTS(
                            SELECT 1
                            FROM records
                            WHERE user_id = $1
                                AND map_code = $2
                                AND verified
                                AND NOT legacy
                                AND wr_xp_check
                        )
                    """
                    exists = await itx.client.database.fetchval(query, search.user_id, search.map_code)
                    log.debug(f"WR Exists: {exists} %s %s", search.user_id, search.map_code)
                    if not exists:
                        query = """
                            UPDATE records
                            SET wr_xp_check = TRUE
                            WHERE user_id = $1
                            AND map_code = $2
                            AND hidden_id = $3
                            AND verified
                            AND NOT legacy
                        """
                        log.debug("Updating WR in db %s %s", search.user_id, search.map_code)
                        await itx.client.database.execute(query, search.user_id, search.map_code, itx.message.id)
                        await itx.client.xp_manager.grant_user_xp_type(search.user_id, "World Record")

                else:  # Non WR Record
                    log.debug("<- Record (Non WR) %s %s", search.user_id, search.map_code)
                    query = """
                        SELECT count(*)
                        FROM records
                        WHERE user_id = $1
                            AND map_code = $2
                            AND verified
                            AND video IS NOT NULL
                            AND NOT wr_xp_check
                            AND NOT legacy
                            AND NOT completion
                    """
                    count = await itx.client.database.fetchval(query, search.user_id, search.map_code)
                    log.debug(f"Record NON-WR count: {count} %s %s", search.user_id, search.map_code)
                    if count == 1:
                        await itx.client.xp_manager.grant_user_xp_type(search.user_id, "Record")

        else:
            data = self.rejected(itx.user.mention, search, rejection)
            await self._remove_record_by_hidden_id(itx.client.database, itx.message.id)

        await original_message.edit(content=data["edit"])

        await itx.client.notification_manager.notify_dm(
            record_submitter.id,
            constants.Notification.DM_ON_VERIFICATION,
            f"`{'- ' * 14}`\n{data['direct_message']}\n`{'- ' * 14}`",
        )
        await itx.message.delete()

    async def _process_map_mastery(self, itx: discord.Interaction[core.Genji], search: models.Record) -> None:
        async with itx.client.session.get(
            f"http://genji-api/v1/mastery/{search.user_id}", headers={"X-API-KEY": GENJI_API_KEY}
        ) as resp:
            map_mastery = await resp.json()
        for map_ in map_mastery:
            query = """
                        INSERT INTO map_mastery (user_id, map_name, medal)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, map_name)
                        DO UPDATE
                        SET medal = excluded.medal
                        WHERE map_mastery.medal IS DISTINCT FROM excluded.medal
                        RETURNING
                            *,
                            CASE
                                WHEN xmax::text::int = 0 THEN 'inserted'
                                ELSE 'updated'
                            END AS operation_status;
                    """
            res = await itx.client.database.fetchrow(query, search.user_id, map_["map_name"], map_["level"])
            if res:
                if res["medal"] == "Placeholder":
                    continue
                assert search.user_id
                nickname = await itx.client.database.fetch_nickname(search.user_id)
                embed = discord.Embed(
                    description=f"{nickname} received the **{res['map_name']} {res['medal']}** Map Mastery badge!",
                )
                embed.set_thumbnail(url=f"https://genji.pk/{map_['icon_url']}")
                assert itx.guild
                xp_channel = itx.guild.get_channel(1324496532447166505)
                assert isinstance(xp_channel, discord.TextChannel)
                await itx.client.notification_manager.notify_channel_default_to_no_ping(
                    xp_channel,
                    search.user_id,
                    constants.Notification.PING_ON_MASTERY,
                    "",
                    embed=embed,
                )

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
            search.record = f"{search.record} - Completion"

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

    @staticmethod
    async def _remove_record_by_hidden_id(db: asyncpg.Connection, hidden_id: int) -> None:
        query = "DELETE FROM records WHERE hidden_id = $1 AND verified IS FALSE;"
        await db.execute(query, hidden_id)


ALERT = (
    # "Don't like these alerts? "
    # "Turn it off by using the command `/alerts false`.\n"
    "You can change your display name " "for records in the bot with the command `/name`!"
)
