from __future__ import annotations

import enum
import functools
import io
import re
from typing import TYPE_CHECKING

import discord
import matplotlib.pyplot as plt
from matplotlib import ticker

import database
import utils
import views

if TYPE_CHECKING:
    import core


class _ModOnlyOptions(enum.Enum):
    FORCE_ACCEPT = "Force Accept"
    FORCE_DENY = "Force Deny"
    APPROVE = "Approve Submission"
    START_OVER = "Start Process Over"

    @classmethod
    def get_all(cls):
        return [
            (
                cls.FORCE_ACCEPT.value,
                "Force submission through, overwriting difficulty votes.",
            ),
            (
                cls.FORCE_DENY.value,
                "Deny submission, deleting it and any associated completions/votes.",
            ),
            (
                cls.APPROVE.value,
                "Approve map submission, signing off on all difficulty votes.",
            ),
            (
                cls.START_OVER.value,
                "Remove all completions and votes for a map without deleting the submission.",
            ),
        ]


class MapSubmitSelection(discord.ui.Select):
    async def callback(self, itx: discord.Interaction[core.Genji]):
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
        data: utils.MapSubmission,
        client: core.Genji,
    ):
        super().__init__(timeout=None)
        self.client = client
        self.data = data
        self.base_diff = data.difficulty
        self.required_votes = self._required_votes()
        self.mod_options = {
            _ModOnlyOptions.FORCE_ACCEPT.value: self.force_accept,
            _ModOnlyOptions.FORCE_DENY.value: self.force_deny,
            _ModOnlyOptions.APPROVE.value: self.approve_submission,
            _ModOnlyOptions.START_OVER.value: self.start_process_over,
        }

    def _required_votes(self) -> int:
        if self.base_diff in utils.DIFFICULTIES[4:6]:
            requirement = 3
        elif self.base_diff in utils.DIFFICULTIES[6:]:
            requirement = 2
        else:
            requirement = 5
        return requirement

    async def _interaction_check(self, itx: discord.Interaction[core.Genji]) -> bool:
        return await self.check_creator(itx) and await self.check_for_completion(itx)

    async def check_for_completion(self, itx: discord.Interaction[core.Genji]) -> bool:
        res = bool(
            await self.client.database.get_row(
                "SELECT 1 FROM records WHERE user_id = $1 AND map_code = $2",
                itx.user.id,
                self.data.map_code,
            )
        )
        if not res:
            await itx.followup.send(
                "You cannot vote here. You cannot vote for your own map or your rank is too low.",
                ephemeral=True,
            )
        return res

    async def check_creator(self, itx: discord.Interaction[core.Genji]) -> bool:
        res = False
        author = await self.client.database.get_row(
            "SELECT rank FROM users WHERE user_id = $1",
            itx.user.id,
        )
        if itx.user.id != self.data.creator.id:
            res = True
            if self.base_diff == "Hell" and author.rank < 6:
                res = False
        if not res:
            await itx.followup.send(
                "You cannot vote before submitting a completion.",
                ephemeral=True,
            )
        return res

    @discord.ui.select(
        options=options,
        placeholder="What difficulty would you rate this map?",
        custom_id="diff_voting",
        row=0,
    )
    async def difficulties(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        await itx.response.defer(ephemeral=True)
        await self._interaction_check(itx)
        if not await self.check_grandmaster(itx):
            return

        await self.set_select_vote_value(itx, select)

        await itx.followup.send(
            f"You voted: {select.values[0]}",
            ephemeral=True,
        )

        count, image = await self.get_plot_data(itx)

        await itx.message.edit(
            embed=itx.message.embeds[0].set_image(url="attachment://vote_chart.png"),
            attachments=[image],
        )

        await self.check_status(itx, count)

    async def get_plot_data(self, itx: discord.Interaction[core.Genji]):
        row = await itx.client.database.get_row(
            """
                SELECT AVG(value) as value, SUM(CASE WHEN user_id != $2 THEN 1 ELSE 0 END) as count
                FROM playtest 
                WHERE message_id = $1;
                """,
            itx.message.id,
            self.data.creator.id,
        )
        avg = row.value
        count = row.count
        func = functools.partial(self.plot, avg)
        self.data.difficulty = utils.convert_num_to_difficulty(avg)

        image = await itx.client.loop.run_in_executor(None, func)
        return count, image

    async def set_select_vote_value(self, itx: discord.Interaction[core.Genji], select: discord.ui.Select):
        vote_value = int(select.values[0]) * 11 / 17
        await self.update_playtest_vote(itx, vote_value)

    @staticmethod
    async def check_grandmaster(itx: discord.Interaction[core.Genji]) -> bool:
        role = itx.guild.get_role(utils.Roles.GRANDMASTER)
        sensei = itx.guild.get_role(utils.STAFF)
        if role not in itx.user.roles or sensei not in itx.user.roles:
            await itx.followup.send(
                content=f"You must be {role.mention} to vote.",
                ephemeral=True,
            )
            return False
        return True

    async def update_playtest_vote(
        self, itx: discord.Interaction[core.Genji], vote_value: float
    ):
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

    async def check_status(self, itx: discord.Interaction[core.Genji], count: int):
        records = await self.get_records_for_map()
        if count >= self.required_votes and len(records) >= self.required_votes:
            self.ready_up_button.disabled = False
            await itx.message.edit(view=self)
            # TODO: approve map process
            # await self.approve_map(itx)

    async def get_records_for_map(self) -> list[database.DotRecord | None]:
        return [
            x
            async for x in self.client.database.get(
                """
                SELECT * FROM records r LEFT JOIN users u ON u.user_id = r.user_id 
                WHERE map_code = $1 and rank >= $2 and r.user_id != $3;
                """,
                self.data.map_code,
                5 if self.base_diff != "Hell" else 6,
                self.data.creator.id,
            )
        ]

    async def approve_map(self, itx: discord.Interaction[core.Genji]):
        self.stop()
        record = await self.get_author_db_row()
        await self.lock_and_archive_thread(record.thread_id)
        author = itx.guild.get_member(self.data.creator.id)
        votes_db_rows = await self.get_votes_for_map()
        difficulty = await self.get_difficulty(votes_db_rows)
        if difficulty in utils.allowed_difficulties(await self.get_creator_rank()):
            await self.post_new_map(author, itx, record.original_msg, votes_db_rows)
        else:
            await self.delete_map_from_db()
            if author:
                await self.send_denial_to_author(author)
        await self.delete_playtest_db_entry()

    async def get_author_db_row(self) -> database.DotRecord:
        return await self.client.database.get_row(
            "SELECT * FROM playtest WHERE map_code=$1 AND user_id=$2;",
            self.data.map_code,
            self.data.creator.id,
        )

    async def lock_and_archive_thread(self, thread_id: int):
        await self.client.get_channel(utils.PLAYTEST).get_thread(thread_id).edit(
            archived=True, locked=True
        )

    async def get_votes_for_map(self) -> list[database.DotRecord | None]:
        return [
            x
            async for x in self.client.database.get(
                """SELECT * FROM playtest WHERE map_code=$1""",
                self.data.map_code,
            )
        ]

    @staticmethod
    async def get_difficulty(votes_db_rows: list[database.DotRecord | None]) -> str:
        vote_values = [x.value for x in votes_db_rows]
        return utils.convert_num_to_difficulty(sum(vote_values) / len(vote_values))

    async def get_creator_rank(self) -> int:
        return await utils.Roles.find_highest_rank(
            self.client.get_guild(utils.GUILD_ID).get_member(self.data.creator.id)
        )

    async def post_new_map(
        self,
        author: discord.Member,
        itx: discord.Interaction[core.Genji],
        original_msg: int,
        votes: list[database.DotRecord | None],
    ):
        await self.set_map_to_official()
        await self.set_map_ratings(votes)
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

    async def set_map_to_official(self):
        await self.client.database.set(
            """UPDATE maps SET official=TRUE WHERE map_code=$1;""",
            self.data.map_code,
        )

    async def set_map_ratings(self, votes: list[database.DotRecord]):
        votes_args = [
            (self.data.map_code, x.user_id, x.value)
            for x in votes
            if x.user_id != self.data.creator.id
        ]
        await self.client.database.set_many(
            """
            INSERT INTO map_ratings (map_code, user_id, difficulty) 
                VALUES($1, $2, $3);
            """,
            votes_args,
        )

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

    def generate_new_embed(self, itx: discord.Interaction[core.Genji]):
        queue = await utils.get_map_info(self.client, itx.message.id)
        if not queue:
            return
        data = queue[0]
        utils.MapSubmission(
            creator=await utils.transform_user(self.client, data.user_id),
            map_code=data.map_code,
            map_name=data.map_name,
            checkpoint_count=data.checkpoints,
            description=data.desc,
            guides=data.guide,
            medals=(data.gold, data.silver, data.bronze),
            map_types=data.map_types,
            mechanics=data.mechanics,
            restrictions=data.restrictions,
            difficulty=utils.convert_num_to_difficulty(data.value),
        ).to_dict()



    async def delete_map_from_db(self):
        await self.client.database.set(
            """DELETE FROM maps WHERE map_code=$1;""",
            self.data.map_code,
        )

    @staticmethod
    async def send_denial_to_author(author: discord.Member):
        await author.send(
            "Your map has been voted higher in difficulty "
            "than your rank allows.\n"
            "Either edit the map that aligns with your current role, "
            "or wait to submit until you have achieved the necessary role."
        )

    async def delete_playtest_db_entry(
        self,
    ):
        await self.client.database.set(
            """DELETE FROM playtest WHERE map_code=$1;""",
            self.data.map_code,
        )

    @discord.ui.button(
        label="Finalize Submission (Creator Only)",
        style=discord.ButtonStyle.red,
        row=3,
        disabled=True,
    )
    async def ready_up_button(self, itx: discord.Interaction[core.Genji]):
        await itx.response.defer(ephemeral=True)
        if itx.user.id != self.data.creator.id:
            return

        await self.send_verification_embed(itx)

    async def send_verification_embed(self, itx: discord.Interaction[core.Genji]):
        embed = utils.GenjiEmbed(
            title=f"{itx.client.cache.users[self.data.creator.id].nickname} has marked a map as ready ({self.data.map_code})!",
            url=itx.message.jump_url,
            description=(
                "Click the link to go to the playtest thread.\n"
                "The following can be done at any time:"
                "- `Force Accept` Override all votes with a chosen difficulty.\n"
                "- `Force Deny` Delete submission and remove completely.\n"
                "The following can be used after the creator has marked the map as ready:\n"
                "- `Approve Submission` Certify that the creator hasn't made "
                "breaking changes to the map after getting votes.\n"
                "- `Start Process Over` Remove all prior completions and votes.\n"
            ),
        )
        await itx.client.get_channel(utils.VERIFICATION_QUEUE).send(embed=embed)

    @discord.ui.select(
        placeholder="Sensei Only Options",
        options=[
            discord.SelectOption(label=option, value=option, description=description)
            for option, description in _ModOnlyOptions.get_all()
        ],
        row=4,
    )
    async def sensei_only_select(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        await self.mod_options[select.values[0]](itx)

    async def force_accept(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(
            itx,
            preceeding_items={
                "difficulty": DifficultySelect(
                    [
                        discord.SelectOption(label=x, value=x)
                        for x in utils.allowed_difficulties(7)
                    ]
                )
            },
        )

        await itx.response.send_message(f"{itx.user.mention}, choose a difficulty.", view=view, ephemeral=True)

        await view.wait()
        if not view.value:
            return

        self.stop()

        await self.remove_votes()
        await self.set_select_vote_value(itx, view.difficulty)
        votes_db_rows = await self.get_votes_for_map()

        record = await self.get_author_db_row()
        await self.lock_and_archive_thread(record.thread_id)
        author = itx.guild.get_member(self.data.creator.id)

        await self.post_new_map(author, itx, record.original_msg, votes_db_rows)
        await self.delete_playtest_db_entry()

    async def force_deny(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            "Are you sure you want to Force Deny this submission? \n"
            "Doing so will remove all records and votes as well as delete the entire submission.",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        self.stop()
        author = itx.guild.get_member(self.data.creator.id)
        await self.delete_map_from_db()
        if author:
            await self.send_denial_to_author(author)
        await self.delete_playtest_db_entry()

    async def approve_submission(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            "Are you sure you want to Approve this submission?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        self.stop()
        votes_db_rows = await self.get_votes_for_map()
        record = await self.get_author_db_row()
        author = itx.guild.get_member(self.data.creator.id)
        await self.post_new_map(author, itx, record.original_msg, votes_db_rows)
        await self.delete_playtest_db_entry()

    async def start_process_over(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            "Are you sure you want to Start the Process Over for this submission? \n"
            "Doing so will remove all records and votes.",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await self.remove_votes()
        await self.remove_records()
        self.ready_up_button.disabled = True
        _, image = await self.get_plot_data(itx)
        await itx.message.edit(
            embed=itx.message.embeds[0].set_image(url="attachment://vote_chart.png"),
            attachments=[image],
            view=self,
        )
        author = itx.guild.get_member(self.data.creator.id)
        await author.send(
            "Your map submission process has been reset by a Sensei.\n"
            "All records and votes have been removed.\n"
            "This usually happens when your map has breaking changes which void current votes."
            f"{itx.message.jump_url}"
        )

    async def remove_votes(self):
        await self.client.database.set(
            "DELETE FROM playtest WHERE map_code = $1 AND user_id != $2;",
            self.data.map_code,
            self.data.creator.id,
        )

    async def remove_records(self):
        await self.client.database.set(
            "DELETE FROM records WHERE map_code = $1",
            self.data.map_code,
        )
        await self.client.database.set(
            "DELETE FROM records_queue WHERE map_code = $1",
            self.data.map_code,
        )
