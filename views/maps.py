from __future__ import annotations

import functools
import io
import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
import matplotlib.pyplot as plt
from matplotlib import ticker

from matplotlib.ticker import MaxNLocator

import utils

if TYPE_CHECKING:
    import core


class MapSubmitSelection(discord.ui.Select):
    async def callback(self, itx: core.Interaction[core.Genji]):
        await itx.response.defer(ephemeral=True)
        for x in self.options:
            x.default = x.value in self.values
        await self.view.map_submit_enable()


class MapTypeSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map type(s)?",
            max_values=len(options),
        )


class DifficultySelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="What difficulty?",
        )


class MechanicsSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map mechanic(s)?",
            max_values=len(options),
        )


class RestrictionsSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map restriction(s)?",
            max_values=len(options),
        )


class PlaytestVoting(discord.ui.View):

    options = [
        discord.SelectOption(label=x, value=str(i))
        for i, x in enumerate(utils.DIFFICULTIES_EXT)
    ]

    def __init__(
        self,
        map_code: str,
        base_diff: str,
        author_id: int,
        client: core.Genji,
        original_msg: int,
    ):
        super().__init__(timeout=None)
        self.map_code = map_code
        self.base_diff = base_diff
        self.author_id = author_id
        self.client = client
        self.author_rank = None
        self.message_id = original_msg

    async def interaction_check(self, itx: core.Interaction[core.Genji]) -> bool:
        res = False
        author = await self.client.database.get_row(
            "SELECT * FROM users WHERE user_id = $1",
            itx.user.id,
        )
        if itx.user.id != self.author_id:
            res = True
            if self.base_diff == "Hell" and author.rank < 6:  # TODO: Test
                res = False
                self.author_rank = author.rank
        return res

    async def check_status(self, itx: core.Interaction[core.Genji], votes: int):
        query = """
        SELECT * FROM records r LEFT JOIN users u ON u.user_id = r.user_id 
        WHERE map_code = $1 and rank >= $2 and r.user_id != $3;
        """

        records = [
            x
            async for x in await itx.client.database.get(
                query,
                self.map_code,
                5 if self.base_diff != "Hell" else 6,
                self.author_id,
            )
        ]

        if (
            (
                self.base_diff in utils.DIFFICULTIES[0:4]
                and votes == 5
                and len(records) == 5
            )
            or (
                self.base_diff in utils.DIFFICULTIES[4:6]
                and votes == 3
                and len(records) == 3
            )
            or (
                self.base_diff in utils.DIFFICULTIES[6:]
                and votes == 2
                and len(records) == 2
            )
        ):
            self.stop()
            record = await itx.client.database.get_row(
                "SELECT * FROM playtest WHERE map_code=$1 AND user_id=$2;",
                self.map_code,
                self.author_id,
            )
            await itx.client.get_channel(utils.PLAYTEST).get_thread(
                record.thread_id
            ).edit(archived=True, locked=True)
            await itx.client.get_channel(utils.PLAYTEST).get_partial_message(
                record.original_msg
            ).delete()

            votes = [
                x
                async for x in itx.client.database.get(
                    """SELECT * FROM playtest WHERE map_code=$1""",
                    self.map_code,
                )
            ]
            vote_values = [x.value for x in votes]
            difficulty = utils.convert_num_to_difficulty(
                sum(vote_values) / len(vote_values)
            )
            author = itx.guild.get_member(self.author_id)

            if difficulty in utils.allowed_difficulties(self.author_rank):
                # Approved map
                await itx.client.database.set(
                    """UPDATE maps SET official=TRUE WHERE map_code=$1;""",
                    self.map_code,
                )

                votes = [
                    (self.map_code, x.user_id, utils.DIFFICULTIES_RANGES[x.value][0])
                    for x in votes
                    if x.user_id != self.author_id
                ]

                await itx.client.database.set_many(
                    """
                    INSERT INTO map_ratings (map_code, user_id, difficulty) 
                        VALUES($1, $2, $3);
                        -- ON CONFLICT (map_code, user_id) 
                        -- DO UPDATE SET difficulty=$3
                        -- WHERE map_ratings.user_id = EXCLUDED.user_id 
                        -- AND map_ratings.map_code = EXCLUDED.map_code; 
                    """,
                    votes,
                )

                avg = await itx.client.database.get_row(
                    "SELECT AVG(difficulty) avg FROM map_ratings WHERE map_code=$1;",
                    self.map_code,
                ).avg
                # Post new maps channel
                # TODO: FIX EMBED
                new_map_embed = (
                    await itx.guild.get_thread(votes[0].thread_id).fetch_message(
                        votes[0].message_id
                    )
                ).embeds[0]
                new_map_embed.title = "New Map!"
                new_map_embed.set_footer(
                    text="For notification of newly added maps only. "
                    "Data may be out of date. "
                    "Use `/map-search` for the latest info."
                )
                new_map_embed.description = re.sub(
                    r"┣ `Difficulty` (.+)\n┣",
                    f"┣ `Difficulty` {utils.convert_num_to_difficulty(avg)}\n┣",
                    new_map_embed.description,
                )

                new_map_message = await itx.guild.get_channel(utils.NEW_MAPS).send(
                    embed=new_map_embed
                )

                itx.client.dispatch(
                    "newsfeed_new_map", author, new_map_message.jump_url, self.map_code
                )
                await utils.update_affected_users(itx, self.map_code)

            else:
                # Delete map
                await itx.client.database.set(
                    """DELETE FROM maps WHERE map_code=$1;""",
                    self.map_code,
                )
                # Send message to author
                if author:
                    await author.send(
                        "Your map has been voted higher in difficulty "
                        "than your rank allows.\n"
                        "Either edit the map that aligns with your current role, "
                        "or wait to submit until you have achieved the necessary role."
                    )

            await itx.client.database.set(
                """DELETE FROM playtest WHERE map_code=$1;""",
                self.map_code,
            )

    @staticmethod
    def setup(ax):
        ax.spines["right"].set_color("none")
        ax.spines["left"].set_color("none")
        ax.yaxis.set_major_locator(ticker.NullLocator())
        ax.spines["top"].set_color("none")
        ax.xaxis.set_ticks_position("bottom")
        ax.set_xlim(0, 18)
        ax.set_ylim(0, 1)
        ax.patch.set_alpha(0.0)

    def plot(self, avg: int | float):
        # Change scale of average to 18 scale instead of 10
        avg = float(avg) * 18 / 11
        labels_ = [
            "Beginner",
            " ",
            "Easy",
            " ",
            " ",
            "Medium",
            " ",
            " ",
            "Hard",
            " ",
            " ",
            "Very Hard",
            " ",
            " ",
            "Extreme",
            " ",
            "Hell",
        ]
        plt.figure(figsize=(8, 8))
        n = 8
        ax = plt.subplot(n, 1, 5)
        self.setup(ax)
        ax.plot(range(0, 18), [0] * 18, color="White")
        plt.plot(avg, 0.5, "ro", ms=20.75, mfc="r")
        ax.xaxis.set_major_locator(ticker.IndexLocator(base=1, offset=1))
        ax.set_xticklabels(labels_, rotation=90, fontsize=18)
        ax.xaxis.set_tick_params(pad=10)
        plt.xlabel("Average", fontsize=24)
        plt.subplots_adjust(top=1.25)
        plt.margins(y=0)
        b = io.BytesIO()
        plt.savefig(b, format="png")
        plt.close()
        b.seek(0)
        return discord.File(b, filename="vote_chart.png")

    @discord.ui.select(
        options=options,
        placeholder="What difficulty would you rate this map?",
        custom_id="diff_voting",
    )
    async def difficulties(
        self, itx: core.Interaction[core.Genji], select: discord.ui.Select
    ):
        await itx.response.defer(ephemeral=True)
        role = itx.guild.get_role(utils.Roles.GRANDMASTER)
        if role not in itx.user.roles:
            await itx.followup.send(
                content=f"You must be {role.mention} to vote.",
                ephemeral=True,
            )
            return

        vote_value = int(select.values[0]) * 11 / 17

        await itx.client.database.set(
            """
            INSERT INTO playtest (thread_id, message_id, map_code, user_id, value)
            VALUES ($1, $2, $3, $4, $5) 
            ON CONFLICT (user_id, message_id)
            DO UPDATE SET value = $5
            WHERE playtest.user_id = EXCLUDED.user_id
            AND playtest.message_id = EXCLUDED.message_id;
            """,
            itx.channel.id,
            itx.message.id,
            self.map_code,
            itx.user.id,
            vote_value,
        )

        avg = (
            await itx.client.database.get_row(
                """
                SELECT AVG(value) as value
                FROM playtest 
                WHERE message_id = $1;
                """,
                itx.message.id,
            )
        ).value

        func = functools.partial(self.plot, avg)
        image = await itx.client.loop.run_in_executor(None, func)

        await itx.message.edit(
            embed=itx.message.embeds[0].set_image(url="attachment://vote_chart.png"),
            attachments=[image],
        )
