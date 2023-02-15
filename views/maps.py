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

import database
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
        # map_code: str,
        # base_diff: str,
        # author_id: int,
        data: utils.MapSubmission,
        client: core.Genji,
        original_msg: int,
        # author_rank: int,
    ):
        super().__init__(timeout=None)
        # self.map_code = map_code
        # self.base_diff = base_diff
        # self.author_id = author_id
        self.client = client
        # self.author_rank = author_rank
        self.message_id = original_msg
        self.data = data
        self.required_votes = self._required_votes()
        self.base_diff = data.difficulty

    def _required_votes(self) -> int:
        if self.base_diff in utils.DIFFICULTIES[4:6]:
            requirement = 3
        elif self.base_diff in utils.DIFFICULTIES[6:]:
            requirement = 2
        else:
            requirement = 5
        return requirement

    async def interaction_check(self, itx: core.Interaction[core.Genji]) -> bool:
        res = False
        author = await self.client.database.get_row(
            "SELECT * FROM users WHERE user_id = $1",
            itx.user.id,
        )

        if itx.user.id != self.data.creator.id:
            res = True
            if self.base_diff == "Hell" and author.rank < 6:
                res = False
        if not res:
            await itx.followup.send(
                "You cannot vote here. You cannot vote for your own map or your rank is too low.",
                ephemeral=True,
            )
        else:
            res = bool(
                await self.client.database.get_row(
                    "SELECT 1 FROM records WHERE user_id = $1 AND map_code = $2",
                    itx.user.id,
                    self.data.map_code,
                )
            )
            if not res:
                await itx.followup.send(
                    "You cannot vote before submitting a completion.",
                    ephemeral=True,
                )
        return res

    async def force_verify_approval(self, itx: core.Interaction[core.Genji]):
        self.stop()
        votes_db_rows = await self.get_votes_for_map(itx)
        record = await self.get_author_db_row(itx)
        author = itx.guild.get_member(self.data.creator.id)
        await self.post_new_map(author, itx, record.original_msg, votes_db_rows)
        await self.delete_playtest_db_entry(itx)

    async def force_deny_approval(self, itx: core.Interaction[core.Genji]):
        self.stop()
        author = itx.guild.get_member(self.data.creator.id)
        await self.delete_map_from_db(itx)
        await self.send_denial_to_author(author)
        await self.delete_playtest_db_entry(itx)

    async def check_status(self, itx: core.Interaction[core.Genji], count: int):
        records = await self.get_records_for_map(itx)
        if count >= self.required_votes and len(records) >= self.required_votes:
            self.ready_up_button.disabled = False
            await itx.message.edit(view=self)
            # await self.approve_map(itx)

    async def get_creator_rank(self):
        return await utils.Roles.find_highest_rank(
            self.client.get_guild(utils.GUILD_ID).get_member(self.data.creator.id)
        )

    async def approve_map(self, itx):
        self.stop()
        record = await self.get_author_db_row(itx)
        await self.lock_and_archive_thread(itx, record.thread_id)
        author = itx.guild.get_member(self.data.creator.id)
        votes_db_rows = await self.get_votes_for_map(itx)
        difficulty = await self.get_difficulty(votes_db_rows)
        if difficulty in utils.allowed_difficulties(await self.get_creator_rank()):
            await self.post_new_map(author, itx, record.original_msg, votes_db_rows)
        else:
            await self.delete_map_from_db(itx)
            await self.send_denial_to_author(author)
        await self.delete_playtest_db_entry(itx)

    async def delete_playtest_db_entry(self, itx: core.Interaction[core.Genji]):
        await itx.client.database.set(
            """DELETE FROM playtest WHERE map_code=$1;""",
            self.data.map_code,
        )

    @staticmethod
    async def get_difficulty(votes_db_rows: list[database.DotRecord | None]) -> str:
        vote_values = [x.value for x in votes_db_rows]
        return utils.convert_num_to_difficulty(sum(vote_values) / len(vote_values))

    async def delete_map_from_db(self, itx: core.Interaction[core.Genji]):
        await itx.client.database.set(
            """DELETE FROM maps WHERE map_code=$1;""",
            self.data.map_code,
        )

    @staticmethod
    async def send_denial_to_author(author: discord.Member | None):
        if author:
            await author.send(
                "Your map has been voted higher in difficulty "
                "than your rank allows.\n"
                "Either edit the map that aligns with your current role, "
                "or wait to submit until you have achieved the necessary role."
            )

    async def post_new_map(
        self,
        author: discord.Member,
        itx: core.Interaction[core.Genji],
        original_msg: int,
        votes: list[database.DotRecord | None],
    ):
        await self.set_map_to_official(itx)
        await self.set_map_ratings(itx, votes)
        avg = (
            await itx.client.database.get_row(
                "SELECT AVG(difficulty) avg FROM map_ratings WHERE map_code=$1;",
                self.data.map_code,
            )
        ).avg
        # Post new maps channel
        thread = itx.guild.get_channel(utils.PLAYTEST)
        thread_msg = await thread.fetch_message(votes[0].thread_id)
        new_map_embed = await self.edit_embed(thread_msg.embeds[0], avg)
        new_map_message = await itx.guild.get_channel(utils.NEW_MAPS).send(
            embed=new_map_embed
        )
        itx.client.dispatch(
            "newsfeed_new_map",
            itx,
            author,
            new_map_message.jump_url,
            self.data.map_code,
        )
        try:
            await utils.update_affected_users(itx, self.data.map_code)
        except Exception as e:
            print("This needs to be excepted:  1----->", e)
        try:
            await itx.client.get_channel(utils.PLAYTEST).get_partial_message(
                original_msg
            ).delete()
        except Exception as e:
            print("This needs to be excepted:  2----->", e)
            ...

    @staticmethod
    async def edit_embed(embed: discord.Embed, avg: float) -> discord.Embed:
        # TODO: Regenerate the entire embed, no need for avg arg if so
        embed.title = "New Map!"
        embed.set_footer(
            text="For notification of newly added maps only. "
            "Data may be wrong or out of date. "
            "Use the /map-search command for the latest info."
        )
        embed.description = re.sub(
            r"┣ `Difficulty` (.+)\n┣",
            f"┣ `Difficulty` {utils.convert_num_to_difficulty(avg)}\n┣",
            embed.description,
        )
        return embed

    async def set_map_ratings(
        self, itx: core.Interaction[core.Genji], votes: list[database.DotRecord]
    ):
        votes_args = [
            (self.data.map_code, x.user_id, x.value)
            for x in votes
            if x.user_id != self.data.creator.id
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
            votes_args,
        )

    async def set_map_to_official(self, itx: core.Interaction[core.Genji]):
        await itx.client.database.set(
            """UPDATE maps SET official=TRUE WHERE map_code=$1;""",
            self.data.map_code,
        )

    async def get_votes_for_map(self, itx: core.Interaction[core.Genji]):
        return [
            x
            async for x in itx.client.database.get(
                """SELECT * FROM playtest WHERE map_code=$1""",
                self.data.map_code,
            )
        ]

    async def get_author_db_row(
        self, itx: core.Interaction[core.Genji]
    ) -> database.DotRecord:
        record = await itx.client.database.get_row(
            "SELECT * FROM playtest WHERE map_code=$1 AND user_id=$2;",
            self.data.map_code,
            self.data.creator.id,
        )
        return record

    @staticmethod
    async def lock_and_archive_thread(
        itx: core.Interaction[core.Genji], thread_id: int
    ):
        await itx.client.get_channel(utils.PLAYTEST).get_thread(thread_id).edit(
            archived=True, locked=True
        )

    async def get_records_for_map(
        self, itx: core.Interaction[core.Genji]
    ) -> list[database.DotRecord | None]:
        return [
            x
            async for x in itx.client.database.get(
                """
                SELECT * FROM records r LEFT JOIN users u ON u.user_id = r.user_id 
                WHERE map_code = $1 and rank >= $2 and r.user_id != $3;
                """,
                self.data.map_code,
                5 if self.base_diff != "Hell" else 6,
                self.data.creator.id,
            )
        ]

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

    def plot(self, avg: int | float) -> discord.File:
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

    # @discord.ui.button(label="Force Verify (Admin Only)", style=discord.ButtonStyle.red, row=4)
    # async def force_verify(self):
    #     ...
    #
    # @discord.ui.button(label="Force Deny (Admin Only)", style=discord.ButtonStyle.red, row=4)
    # async def force_deny(self):
    #     ...

    @discord.ui.button(
        label="Finalize Submission (Creator Only)",
        style=discord.ButtonStyle.red,
        row=4,
        disabled=True,
    )
    async def ready_up_button(self):
        ...

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
            self.data.map_code,
            itx.user.id,
            vote_value,
        )

        await itx.followup.send(
            f"You voted: {select.values[0]}",
            ephemeral=True,
        )

        row = await itx.client.database.get_row(
            """
                SELECT AVG(value) as value, SUM(CASE WHEN user_id != 141372217677053952 THEN 1 ELSE 0 END) as count
                FROM playtest 
                WHERE message_id = $1;
                """,
            itx.message.id,
        )

        avg = row.value
        count = row.count

        func = functools.partial(self.plot, avg)
        image = await itx.client.loop.run_in_executor(None, func)

        await itx.message.edit(
            embed=itx.message.embeds[0].set_image(url="attachment://vote_chart.png"),
            attachments=[image],
        )

        await self.check_status(itx, count)
