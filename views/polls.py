from __future__ import annotations

import io
import typing

import discord
from discord.ext import commands
from matplotlib import pyplot as plt

from utils import constants, embeds

if typing.TYPE_CHECKING:
    import core


class ButtonOnCooldown(commands.CommandError):
    """Button Cooldown error."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after


class PollView(discord.ui.View):
    """Poll view."""

    def __init__(self, labels: list[str], title: str) -> None:
        super().__init__(timeout=None)
        self.labels = labels
        self.title = title
        self.cd = commands.CooldownMapping.from_cooldown(1.0, 15.0, lambda x: x.user)
        self.add_buttons()

    def add_buttons(self) -> None:
        """Add buttons to view."""
        for i, label in enumerate(self.labels, start=1):
            setattr(self, f"option_{i}", PollOptionButton(label, i))
            self.add_item(getattr(self, f"option_{i}"))

    async def interaction_check(self, itx: discord.Interaction[core.Genji]) -> bool:
        """Check interaction for rate limits."""
        retry_after = self.cd.update_rate_limit(itx)
        if retry_after:
            raise ButtonOnCooldown(retry_after)
        return True

    async def on_error(
        self,
        itx: discord.Interaction[core.Genji],
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        """Error handler for PollView."""
        if isinstance(error, ButtonOnCooldown):
            seconds = int(error.retry_after)
            unit = "second" if seconds == 1 else "seconds"
            await itx.response.send_message(
                f"You're on cooldown for {seconds} {unit}!", ephemeral=True
            )
        else:
            await super().on_error(itx, error, item)

    @discord.ui.button(
        label="End Poll (Sensei Only)",
        style=discord.ButtonStyle.red,
        custom_id="end_poll",
        row=4,
    )
    async def end(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ) -> None:
        """End poll button callback."""
        if itx.guild.get_role(constants.STAFF) not in itx.user.roles:
            await itx.response.send_message(
                "You are not allowed to pres this button", ephemeral=True
            )
            return
        await itx.response.send_message("Ending poll.", ephemeral=True)
        self.clear_items()
        self.stop()
        await (
            itx.guild.get_channel(itx.channel_id)
            .get_partial_message(itx.message.id)
            .edit(
                view=self,
            )
        )


class PollOptionButton(discord.ui.Button):
    """Poll option button."""

    view: PollView

    def __init__(self, label: str, option_number: int) -> None:
        super().__init__(
            label=label,
            style=discord.ButtonStyle.grey,
            custom_id=label,
        )
        self.option_number = option_number

    async def callback(self, itx: discord.Interaction[core.Genji]) -> None:
        """Poll option voting callback."""
        await itx.response.send_message(
            content=f"You voted for {self.label}!", ephemeral=True
        )
        await self.insert_poll_vote(itx)
        counts = await self.get_all_counts(itx)

        data = {k: v for k, v in zip(self.view.labels, counts) if v != 0}

        chart = await itx.client.loop.run_in_executor(
            None,
            create_graph,
            data,
        )
        embed = await build_embed(self.view.title)

        await (
            itx.guild.get_channel(itx.channel_id)
            .get_partial_message(itx.message.id)
            .edit(
                content=f"**Total Votes:** {sum(counts)}",
                embed=embed,
                attachments=[chart],
            )
        )

    async def insert_poll_vote(self, itx: discord.Interaction[core.Genji]) -> None:
        """Insert poll vote into database."""
        await itx.client.database.set(
            """
            INSERT INTO polls (user_id, option, message_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, message_id)
            DO UPDATE SET option = $2
            WHERE polls.user_id = EXCLUDED.user_id
            AND polls.message_id = EXCLUDED.message_id;
            """,
            itx.user.id,
            self.option_number,
            itx.message.id,
        )

    @staticmethod
    async def get_all_counts(itx: discord.Interaction[core.Genji]) -> list[str]:
        """Get all poll vote counts."""
        query = """
            WITH non_zeros AS (
                SELECT option, count(*)
                FROM polls
                WHERE message_id = $1
                GROUP BY option
            )
            SELECT
               opt.ordinality AS option,
               COALESCE(nz.count, 0) AS count
            FROM
                polls_info pi,
                unnest(pi.options) WITH ORDINALITY AS opt
                LEFT OUTER JOIN non_zeros nz ON opt.ordinality = nz.option
                WHERE message_id = $1
        """
        rows = await itx.client.database.fetch(query, itx.message.id)
        return [x["count"] for x in rows]


def create_graph(data: dict[str, int | float]) -> discord.File:
    """Create graph."""
    fig, ax = plt.subplots()
    labels = []
    percentages = []
    for k, v in data.items():
        if v != 0:
            labels.append(k)
            percentages.append(v)
    ax.pie(
        percentages,
        labels=labels,
        autopct="%1.0f%%",
        wedgeprops={"linewidth": 3, "edgecolor": "white"},
        colors=["#66CD00", "#DC143C", "#9A32CD", "#00688B", "#808A87"],
    )
    plt.legend(labels, loc="best")
    plt.axis("equal")
    data_stream = io.BytesIO()
    plt.savefig(data_stream, format="png", bbox_inches="tight", dpi=80)
    plt.close()
    data_stream.seek(0)
    return discord.File(data_stream, filename="poll.png")


async def build_embed(title: str) -> discord.Embed:
    """Build embed."""
    embed = embeds.GenjiEmbed(title=title)
    embed.set_image(url="attachment://poll.png")
    return embed
