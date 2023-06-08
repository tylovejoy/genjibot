from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord

import views

if TYPE_CHECKING:
    import core

import database
import utils


class RejectReasonModal(discord.ui.Modal, title="Rejection Reason"):
    reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.long)

    async def on_submit(self, itx: discord.Interaction[core.Genji]):
        await itx.response.send_message("Sending reason to user.", ephemeral=True)


class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:accept",
    )
    async def green(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        await itx.response.defer(ephemeral=True)
        await self.verification(itx, True)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.red,
        custom_id="persistent_view:reject",
    )
    async def red(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        modal = RejectReasonModal()
        await itx.response.send_modal(modal)
        await modal.wait()
        await self.verification(itx, False, modal.reason.value)

    async def verification(
        self,
        itx: discord.Interaction[core.Genji],
        verified: bool,
        rejection: str | None = None,
    ):
        """Verify a record."""

        search = await itx.client.database.get_row(
            "SELECT * FROM records rq "
            "LEFT JOIN maps m on rq.map_code = m.map_code "
            "WHERE hidden_id = $1",
            itx.message.id,
        )
        if search.user_id == itx.user.id:
            await itx.followup.send(
                content="You cannot verify your own submissions.", ephemeral=True
            )
            return
        self.clear_items()
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.grey,
                label="Please wait...",
                disabled=True,
                emoji=utils.TIME,
            )
        )
        await itx.edit_original_response(view=self)
        self.stop()
        original_message = await self.find_original_message(
            itx, search.channel_id, search.message_id
        )
        if not original_message:
            return
        await itx.edit_original_response(view=self)
        user = itx.guild.get_member(search.user_id)

        if verified:
            medals = await itx.client.database.get_row(
                """
            SELECT gold, silver, bronze FROM map_medals WHERE map_code = $1;
            """,
                search.map_code,
            )

            if medals:
                medals = [medals.gold, medals.silver, medals.bronze]
                medals = tuple(map(float, medals))
            else:
                medals = (0, 0, 0)

            data = self.accepted(itx, search, medals)
            # TODO:
            await itx.client.database.set(
                """
                UPDATE records SET verified = TRUE WHERE map_code = $1 AND user_id = $2;
                """,
                search.map_code,
                search.user_id,
            )
            if search.official:
                await utils.auto_role(itx.client, itx.guild.get_member(search.user_id))
        else:
            data = self.rejected(itx, search, rejection)
        await original_message.edit(content=data["edit"])

        if (
            views.utils.SettingFlags.VERIFICATION
            in itx.client.cache.users[user.id].flags
        ):
            try:
                await user.send(
                    "`- - - - - - - - - - - - - -`\n"
                    + data["direct_message"]
                    + "\n`- - - - - - - - - - - - - -`"
                )
            except Exception as e:
                itx.client.logger.info(e)
        with contextlib.suppress(discord.NotFound):
            await itx.message.delete()

        if verified:
            query = """
                WITH map AS (SELECT m.map_code,
                        m.map_name,
                        string_agg(distinct (nickname), ', ') as creators
                FROM maps m
                          LEFT JOIN map_creators mc on m.map_code = mc.map_code
                          LEFT JOIN users u on mc.user_id = u.user_id
                GROUP BY m.map_code, m.map_name),
                     ranks AS (SELECT u.nickname,
                                      r.user_id,
                                      record,
                                      screenshot,
                                      video,
                                      verified,
                                      r.map_code,
                                      map.map_name,
                                      map.creators,
                                      RANK() OVER (
                                          PARTITION BY r.map_code
                                          ORDER BY record
                                          ) rank_num
                               FROM records r
                                        LEFT JOIN users u
                                                  on r.user_id = u.user_id
                                        LEFT JOIN map on map.map_code = r.map_code)
                SELECT *
                FROM ranks
                WHERE user_id = $1 AND map_code = $2
                -- AND rank_num = 1 
                AND verified = TRUE AND video IS NOT NULL;
            """
            res = await itx.client.database.get_row(
                query, search.user_id, search.map_code
            )

            if res:
                itx.client.dispatch("newsfeed_record", itx, res, medals)

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
        itx: discord.Interaction[core.Genji],
        search: database.DotRecord,
        medals: tuple[float, float, float],
    ) -> dict[str, str]:
        """Data for verified records."""
        if float(search.record) == utils.COMPLETION_PLACEHOLDER:
            search.record = "Completion"
        icon = utils.icon_generator(search, medals)
        record = f"**Record:** {search.record} " f"{icon}"
        if search.video:
            edit = f"{icon} Complete verification by {itx.user.mention}!"
        else:
            edit = (
                f"{icon} Partial verification by {itx.user.mention}! "
                f"No video proof supplied."
            )
        return {
            "edit": edit,
            "direct_message": (
                f"**Map Code:** {search.map_code}\n"
                + record
                + f"verified by {itx.user.mention}!\n\n"
                + ALERT
            ),
        }

    @staticmethod
    def rejected(
        itx: discord.Interaction[core.Genji],
        search: database.DotRecord,
        rejection: str,
    ) -> dict[str, str]:
        """Data for rejected records."""
        if float(search.record) == utils.COMPLETION_PLACEHOLDER:
            search.record = "Completion"

        record = f"**Record:** {search.record}\n"

        return {
            "edit": f"{utils.UNVERIFIED} " f"Rejected by {itx.user.mention}!",
            "direct_message": (
                f"**Map Code:** {search.map_code}\n"
                + record
                + f"Your record got {utils.UNVERIFIED} "
                f"rejected by {itx.user.mention}!\n\n"
                f"**Reason:** {rejection}\n\n" + ALERT
            ),
        }


ALERT = (
    # "Don't like these alerts? "
    # "Turn it off by using the command `/alerts false`.\n"
    "You can change your display name "
    "for records in the bot with the command `/name`!"
)
