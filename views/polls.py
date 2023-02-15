from __future__ import annotations

import io
import typing

import discord
from discord.ext import commands
from matplotlib import pyplot as plt

import utils

if typing.TYPE_CHECKING:
    import core


class ButtonOnCooldown(commands.CommandError):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after


class PollView(discord.ui.View):
    def __init__(self, labels: list[str], title: str):
        super().__init__(timeout=None)
        self.labels = labels
        self.title = title
        self.cd = commands.CooldownMapping.from_cooldown(1.0, 15.0, lambda x: x.user)
        self.add_buttons()

    def add_buttons(self):
        for i, label in enumerate(self.labels, start=1):
            setattr(self, f"option_{i}", PollOptionButton(label, i))
            self.add_item(getattr(self, f"option_{i}"))

    async def interaction_check(self, itx: core.Interaction[core.Genji]):
        retry_after = self.cd.update_rate_limit(itx)
        if retry_after:
            raise ButtonOnCooldown(retry_after)
        return True

    async def on_error(
        self, itx: core.Interaction[core.Genji], error: Exception, item: discord.ui.Item
    ):
        if isinstance(error, ButtonOnCooldown):
            seconds = int(error.retry_after)
            unit = "second" if seconds == 1 else "seconds"
            await itx.response.send_message(
                f"You're on cooldown for {seconds} {unit}!", ephemeral=True
            )
        else:
            await super().on_error(itx, error, item)

    @discord.ui.button(label="End Poll (Sensei Only)", style=discord.ButtonStyle.red)
    async def end(self, itx: core.Interaction[core.Genji], button: discord.ui.Button):
        if itx.guild.get_role(utils.STAFF) not in itx.user.roles:
            await itx.response.send_message(
                "You are not allowed to pres this button", ephemeral=True
            )
            return
        await itx.response.send_message("Ending poll.", ephemeral=True)
        self.clear_items()
        self.stop()
        await itx.guild.get_channel(itx.channel_id).get_partial_message(
            itx.message.id
        ).edit(
            view=self,
        )


class PollOptionButton(discord.ui.Button):
    view: PollView

    def __init__(self, label: str, option_number: int):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.grey,
            custom_id=label,
        )
        self.option_number = option_number

    async def callback(self, itx: core.Interaction[core.Genji]):
        await itx.response.send_message(
            content=f"You voted for {self.label}!", ephemeral=True
        )
        await self.insert_poll_vote(itx)
        counts = await self.get_all_counts(itx)

        data = {
            k: v
            for k, v in zip(self.view.labels, convert_counts_to_percentage(counts))
            if v != 0
        }

        chart = await itx.client.loop.run_in_executor(
            None,
            create_graph,
            data,
        )
        embed = await build_embed(self.view.title)

        await itx.guild.get_channel(itx.channel_id).get_partial_message(
            itx.message.id
        ).edit(
            content=f"**Total Votes:** {sum(data.values())}",
            embed=embed,
            attachments=[chart],
        )

    async def insert_poll_vote(self, itx):
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

    async def get_all_counts(self, itx):
        return [
            x.count
            async for x in itx.client.database.get(
                """
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
            """,
                itx.message.id,
            )
        ]


def create_graph(data: dict[str, int | float]) -> discord.File:
    plt.style.use("seaborn-dark-palette")
    fig, ax = plt.subplots()
    labels = [k for k, v in data.items() if v != 0]
    percentages = [v for v in data.values() if v != 0]
    ax.pie(percentages, labels=labels, autopct="%1.0f%%")
    plt.legend(labels, loc="best")
    plt.axis("equal")
    data_stream = io.BytesIO()
    plt.savefig(data_stream, format="png", bbox_inches="tight", dpi=80)
    plt.close()
    data_stream.seek(0)
    return discord.File(data_stream, filename="poll.png")


def convert_counts_to_percentage(counts: list[int]) -> list[float]:
    total = sum(counts)
    percentages = [total / count if count > 0 else 0.0 for count in counts]
    return percentages


async def build_embed(title: str) -> discord.Embed:
    embed = utils.GenjiEmbed(title=title)
    embed.set_image(url="attachment://poll.png")
    return embed
