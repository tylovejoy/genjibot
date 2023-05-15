from __future__ import annotations

import enum
import functools
import io
from typing import TYPE_CHECKING

import discord
import matplotlib.pyplot as plt
from discord import ButtonStyle

import database
import utils
import views
from utils import PLAYTEST

if TYPE_CHECKING:
    import core


colors = {
    "Beginner": "#B9FFB7",
    "Easy -": "#00ff1a",
    "Easy": "#00ff1a",
    "Easy +": "#00ff1a",
    "Medium -": "#cdff3a",
    "Medium": "#cdff3a",
    "Medium +": "#cdff3a",
    "Hard -": "#fbdf00",
    "Hard": "#fbdf00",
    "Hard +": "#fbdf00",
    "Very Hard -": "#ff9700",
    "Very Hard": "#ff9700",
    "Very Hard +": "#ff9700",
    "Extreme -": "#ff4500",
    "Extreme": "#ff4500",
    "Extreme +": "#ff4500",
    "Hell": "#ff0000",
}


class _ModOnlyOptions(enum.Enum):
    FORCE_ACCEPT = "Force Accept"
    FORCE_DENY = "Force Deny"
    APPROVE = "Approve Submission"
    START_OVER = "Start Process Over"
    REMOVE_COMPLETIONS = "Remove Completions"
    REMOVE_VOTES = "Remove Votes"
    TOGGLE_FINALIZE_BUTTON = "Toggle Finalize Button"

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
            (
                cls.REMOVE_COMPLETIONS.value,
                "Remove all completions for a map without deleting the submission.",
            ),
            (
                cls.REMOVE_VOTES.value,
                "Remove all votes for a map without deleting the submission.",
            ),
            (
                cls.TOGGLE_FINALIZE_BUTTON.value,
                "Enable/Disable the Finalize button for the creator to use.",
            ),
        ]


class MapSubmitSelection(discord.ui.Select):
    view: views.ConfirmBaseView

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
            min_values=0,
            max_values=len(options),
        )


class RestrictionsSelect(MapSubmitSelection):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            options=options,
            placeholder="Map restriction(s)?",
            min_values=0,
            max_values=len(options),
        )


class PlaytestVoting(discord.ui.View):
    options = [
        discord.SelectOption(label=x, value=str(i))
        for i, x in enumerate(utils.DIFFICULTIES_EXT)
    ] + [discord.SelectOption(label="Remove My Vote", value=str("REMOVE"))]

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
            _ModOnlyOptions.REMOVE_COMPLETIONS.value: self.remove_votes_option,
            _ModOnlyOptions.REMOVE_VOTES.value: self.remove_votes_option,
            _ModOnlyOptions.TOGGLE_FINALIZE_BUTTON.value: self.toggle_finalize_button,
        }

    def change_difficulty(self, difficulty: int):
        _difficulty = utils.convert_num_to_difficulty(difficulty)
        self.base_diff = _difficulty
        self.required_votes = self._required_votes()

    def _required_votes(self) -> int:
        if "Hell" in self.base_diff:
            requirement = 1
        elif "Extreme" in self.base_diff:
            requirement = 2
        elif "Very Hard" in self.base_diff:
            requirement = 3
        else:
            requirement = 5
        return requirement

    async def _interaction_check(self, itx: discord.Interaction[core.Genji]) -> bool:
        if is_creator := await self.check_creator(itx):
            await itx.followup.send(
                "You cannot vote for your own map.",
                ephemeral=True,
            )

        is_sensei = await self.check_sensei(itx)
        return not is_creator and (is_sensei or await self.check_for_completion(itx))

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
                "You cannot vote before submitting a completion.",
                ephemeral=True,
            )
        return res

    async def check_creator(self, itx: discord.Interaction[core.Genji]) -> bool:
        return itx.user.id == self.data.creator.id

    @staticmethod
    async def check_sensei(itx: discord.Interaction[core.Genji]) -> bool:
        return itx.guild.get_role(utils.STAFF) in itx.user.roles

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
        if not await self._interaction_check(itx):
            return

        if select.values[0] == "REMOVE":
            await self.delete_user_vote(itx, itx.user.id)
            diff_string = select.values[0]
        else:
            await self.set_select_vote_value(itx, select)
            diff_string = utils.DIFFICULTIES_EXT[int(select.values[0])]

        await itx.followup.send(
            f"You voted: {diff_string}",
            ephemeral=True,
        )

        thread: discord.Thread = itx.channel
        await thread.edit(archived=False, locked=False)
        await thread.add_user(itx.user)

        count, image = await self.get_plot_data(itx)

        await itx.message.edit(
            content=f"Total Votes: {count} / {self.required_votes}",
            embed=itx.message.embeds[0].set_image(url="attachment://vote_chart.png"),
            attachments=[image],
            view=self,
        )
        row = await itx.client.database.get_row(
            "SELECT thread_id FROM playtest WHERE message_id = $1 AND is_author",
            itx.message.id,
        )
        if row:
            await itx.guild.get_channel(PLAYTEST).get_partial_message(
                row.thread_id
            ).edit(
                content=f"Total Votes: {count} / {self.required_votes}",
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

    async def set_select_vote_value(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        vote_value = int(select.values[0]) * 11 / 17
        await self.update_playtest_vote(itx, vote_value)

    async def _set_select_vote_value_creator(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        vote_value = int(select.values[0]) * 11 / 17
        await self._update_user_vote(itx, vote_value, self.data.creator.id)

    async def update_playtest_vote(
        self, itx: discord.Interaction[core.Genji], vote_value: float
    ):
        await self._update_user_vote(itx, vote_value, itx.user.id)

    async def _update_user_vote(
        self, itx: discord.Interaction[core.Genji], vote_value: float, user_id: int
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
            user_id,
            vote_value,
        )

    async def delete_user_vote(
        self, itx: discord.Interaction[core.Genji], user_id: int
    ):
        await itx.client.database.set(
            "DELETE FROM playtest WHERE user_id = $1 AND map_code = $2",
            user_id,
            self.data.map_code,
        )

    @staticmethod
    def plot(avg: int | float):
        avg = float(avg)
        fig, ax = plt.subplots()
        ax.plot([0, 0], [0, 0])

        for k, diff in utils.DIFFICULTIES_RANGES.items():
            if "-" in k:
                ax.add_patch(
                    plt.Rectangle(
                        (diff[0], -3),
                        diff[1] - diff[0],
                        4,
                        color=colors[k[:-2]],
                        alpha=0.3,
                        hatch="\\",
                    )
                )

            elif "+" in k:
                ax.add_patch(
                    plt.Rectangle(
                        (diff[0], -3),
                        diff[1] - diff[0],
                        4,
                        color=colors[k[:-2]],
                        alpha=0.3,
                        hatch="/",
                    )
                )

            else:
                ax.add_patch(
                    plt.Rectangle(
                        (diff[0], -3),
                        diff[1] - diff[0],
                        4,
                        color=colors[k],
                    ),
                )
                plt.text(
                    (diff[0] + diff[1]) / 2,
                    -1.5,
                    k,
                    rotation=90 if k == "Beginner" else 0,
                    horizontalalignment="center",
                    verticalalignment="center",
                )

        plt.axvline(x=avg, ymin=0.55, ymax=0.95, color="black", linestyle="solid")
        plt.plot(avg, -0.7, "ko", ms=15, mfc="black")
        fig.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
        ax.add_patch(
            plt.Rectangle(
                (0, -3),
                10,
                4,
                color="black",
                fill=False,
            ),
        )
        plt.axis("off")
        b = io.BytesIO()
        plt.show()
        plt.savefig(b, format="png")
        plt.close()
        b.seek(0)
        return discord.File(b, filename="vote_chart.png")

    async def mod_check_status(self, count: int, message: discord.Message):
        if (
            count >= self.required_votes
            and self.ready_up_button.style == ButtonStyle.red
        ):
            self.ready_up_button.disabled = False
            await message.edit(view=self)
            await self.data.creator.send(
                f"**{self.data.map_code}** has received enough completions and votes. "
                f"Go to the thread and *Finalize* the submission!"
            )

    async def check_status(self, itx: discord.Interaction[core.Genji], count: int):
        if (
            count >= self.required_votes
            and self.ready_up_button.style == ButtonStyle.red
        ):
            self.ready_up_button.disabled = False
            await itx.message.edit(view=self)
            await self.data.creator.send(
                f"**{self.data.map_code}** has received enough completions and votes. "
                f"Go to the thread and *Finalize* the submission!"
            )

    async def approve_map(self):
        self.stop()
        record = await self.get_author_db_row()
        await self.lock_and_archive_thread(record.thread_id)
        await self.delete_playtest_thread(record.thread_id)
        try:
            await self.delete_playtest_post(record.thread_id)
        except Exception as e:
            print(
                f"{e} || this needs to be caught properly in approve_map views/maps.py"
            )
        author = self.client.get_guild(utils.GUILD_ID).get_member(self.data.creator.id)
        votes_db_rows = await self.get_votes_for_map()
        await self.post_new_map(author, record.original_msg, votes_db_rows)
        try:
            await self.increment_playtest_count(votes_db_rows)
        except Exception as e:
            print(e)

        query = (
            "SELECT verification_id FROM playtest WHERE user_id = $1 AND map_code = $2;"
        )
        row = await self.client.database.get_row(
            query, self.data.creator.id, self.data.map_code
        )
        if row.verification_id:
            await self.client.get_guild(utils.GUILD_ID).get_channel(
                utils.VERIFICATION_QUEUE
            ).get_partial_message(row.verification_id).delete()

        await self.delete_playtest_db_entry()

    async def increment_playtest_count(self, votes_db_rows):
        query = """
            INSERT INTO playtest_count (user_id, amount)
            VALUES ($1, 1)
            ON CONFLICT (user_id) DO UPDATE SET amount = playtest_count.amount + 1;
        """

        await self.client.database.set_many(
            query,
            [(x.user_id,) for x in votes_db_rows if x.user_id != self.data.creator.id],
        )

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

    async def delete_playtest_thread(self, thread_id: int):
        await self.client.get_channel(utils.PLAYTEST).get_thread(thread_id).delete()

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
        original_msg: int,
        votes: list[database.DotRecord | None],
    ):
        await self.set_map_to_official()
        await self.set_map_ratings(votes)
        thread = self.client.get_guild(utils.GUILD_ID).get_channel(utils.PLAYTEST)
        await thread.fetch_message(votes[0].thread_id)
        self.client.dispatch(
            "newsfeed_new_map",
            author,
            self.data,
        )

        try:
            await utils.update_affected_users(self.client, self.data.map_code)
        except Exception as e:
            print("This needs to be excepted:  1----->", e)
        try:
            await self.client.get_channel(utils.PLAYTEST).get_partial_message(
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
                VALUES($1, $2, $3)
            ON CONFLICT (map_code, user_id) 
            DO UPDATE SET difficulty = $3
            WHERE map_ratings.map_code = excluded.map_code and map_ratings.user_id = excluded.user_id;
                ;
            """,
            votes_args,
        )

    async def edit_embed(
        self, embed: discord.Embed, itx: discord.Interaction[core.Genji]
    ) -> discord.Embed:
        embed.title = "New Map!"
        embed.set_footer(
            text="For notification of newly added maps only. "
            "Data may be wrong or out of date. "
            "Use the /map-search command for the latest info."
        )
        embed.description = await self.generate_new_embed_text(itx)
        return embed

    async def generate_new_embed_text(
        self, itx: discord.Interaction[core.Genji]
    ) -> str:
        queue = await utils.get_map_info(self.client, itx.message.id)
        if not queue:
            return ""
        data = queue[0]
        return str(
            utils.MapSubmission(
                creator=await utils.transform_user(self.client, data.creator_ids[0]),
                map_code=data.map_code,
                map_name=data.map_name,
                checkpoint_count=data.checkpoints,
                description=data.desc,
                guides=data.guide,
                medals=(data.gold, data.silver, data.bronze),
                map_types=data.map_type,
                mechanics=data.mechanics,
                restrictions=data.restrictions,
                difficulty=utils.convert_num_to_difficulty(data.value),
            )
        )

    async def delete_map_from_db(self):
        await self.client.database.set(
            """DELETE FROM maps WHERE map_code=$1;""",
            self.data.map_code,
        )

    async def send_denial_to_author(
        self, author: discord.Member, reason: str | None = None
    ):
        await author.send(
            f"The **{self.data.map_code}** map submission has been denied by a Sensei and has been deleted."
            f"\n\n{reason if reason else ''}"
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
        row=2,
        disabled=True,
        custom_id="ready_up",
    )
    async def ready_up_button(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        await itx.response.defer(ephemeral=True)
        if itx.user.id != self.data.creator.id:
            await itx.followup.send("You are not allowed to use this button.")
            return
        await self._set_ready_button(itx, button)
        verification_msg = await self.send_verification_embed(itx)

        query = """UPDATE playtest SET verification_id = $1 WHERE user_id = $2 AND map_code = $3;"""
        await itx.client.database.set(
            query, verification_msg.id, self.data.creator.id, self.data.map_code
        )

    async def _set_ready_button(
        self, itx: discord.Interaction[core.Genji], button: discord.ui.Button
    ):
        button.style = discord.ButtonStyle.green
        button.disabled = True
        button.label = "Ready! Waiting on Sensei response..."
        button.emoji = utils.TIME
        await itx.message.edit(view=self)

    async def _unset_ready_button(
        self,
        itx: discord.Interaction[core.Genji],
        button: discord.ui.Button,
        edit_now: bool = False,
    ):
        button.style = discord.ButtonStyle.red
        button.disabled = True
        button.label = "Finalize Submission (Creator Only)"
        button.emoji = None
        if edit_now:
            await itx.message.edit(view=self)

    async def send_verification_embed(
        self, itx: discord.Interaction[core.Genji]
    ) -> discord.Message:
        embed = utils.GenjiEmbed(
            title=f"{itx.client.cache.users[self.data.creator.id].nickname} "
            f"has marked a map as ready ({self.data.map_code})!",
            url=itx.message.jump_url,
            description=(
                "Click the link to go to the playtest thread.\n"
                "The following can be done at any time:\n"
                "- `Force Accept` Override all votes with a chosen difficulty.\n"
                "- `Force Deny` Delete submission and remove completely.\n"
                "The following can be used after the creator has marked the map as ready:\n"
                "- `Approve Submission` Certify that the creator hasn't made "
                "breaking changes to the map after getting votes.\n"
                "- `Start Process Over` Remove all prior completions and votes.\n"
            ),
        )
        return await itx.client.get_channel(utils.VERIFICATION_QUEUE).send(embed=embed)

    @discord.ui.select(
        placeholder="Sensei Only Options",
        options=[
            discord.SelectOption(label=option, value=option, description=description)
            for option, description in _ModOnlyOptions.get_all()
        ],
        row=1,
        custom_id="sensei_only_select",
    )
    async def sensei_only_select(
        self, itx: discord.Interaction[core.Genji], select: discord.ui.Select
    ):
        if not await self.check_sensei(itx):
            # await itx.followup.send("You cannot use this.", ephemeral=True)
            return
        await itx.message.edit(view=self)
        await self.mod_options[select.values[0]](itx)

    async def force_accept(self, itx: discord.Interaction[core.Genji]):
        if await self.check_creator(itx):
            await itx.response.send_message(
                "You cannot use this if you are the creator.", ephemeral=True
            )
            return

        view = views.Confirm(
            itx,
            preceeding_items={"difficulty": DifficultySelect(self.options)},
        )

        await itx.response.send_message(
            content=f"{itx.user.mention}, choose a difficulty.",
            ephemeral=True,
            view=view,
        )

        await view.wait()
        if not view.value:
            return

        self.stop()

        await self.remove_votes()
        await self._set_select_vote_value_creator(itx, view.difficulty)
        votes_db_rows = await self.get_votes_for_map()

        record = await self.get_author_db_row()
        await self.lock_and_archive_thread(record.thread_id)
        author = itx.guild.get_member(self.data.creator.id)

        await self.post_new_map(author, record.original_msg, votes_db_rows)
        await self.increment_playtest_count(votes_db_rows)
        await self.delete_playtest_db_entry()
        itx.client.playtest_views.pop(itx.message.id)

    async def force_deny(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            content="Are you sure you want to Force Deny this submission? \n"
            "Doing so will remove all records and votes as well as delete the entire submission.",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return
        self.stop()
        author = itx.guild.get_member(self.data.creator.id)
        record = await self.get_author_db_row()
        await self.lock_and_archive_thread(record.thread_id)
        await self.delete_playtest_post(record.thread_id)
        await self.delete_map_from_db()
        if author:
            # TODO: Modal for reason
            await self.send_denial_to_author(author)
        await self.delete_playtest_db_entry()
        itx.client.cache.maps.remove_one(self.data.map_code)
        itx.client.playtest_views.pop(itx.message.id)

    async def delete_playtest_post(self, thread_id: int):
        await self.client.get_channel(utils.PLAYTEST).get_partial_message(
            thread_id
        ).delete()

    async def approve_submission(self, itx: discord.Interaction[core.Genji]):
        if await self.check_creator(itx):
            await itx.response.send_message(
                "You cannot use this if you are the creator.", ephemeral=True
            )
            return
        view = views.Confirm(itx)
        await itx.response.send_message(
            content="Are you sure you want to Approve this submission?",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return

        itx.client.playtest_views.pop(itx.message.id)
        await self.approve_map()

    async def start_process_over(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            content="Are you sure you want to Start the Process Over for this submission? \n"
            "Doing so will remove all records and votes.",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return
        await self.remove_votes()
        await self.remove_records()
        await self._unset_ready_button(itx, self.ready_up_button)
        _, image = await self.get_plot_data(itx)
        await itx.message.edit(
            content="Total Votes: 0",
            embed=itx.message.embeds[0].set_image(url="attachment://vote_chart.png"),
            attachments=[image],
            view=self,
        )
        await itx.message.channel.send(
            "@here, All records and votes have been removed by a Sensei."
        )
        author = itx.guild.get_member(self.data.creator.id)
        await author.send(
            "Your map submission process has been reset by a Sensei.\n"
            "All records and votes have been removed.\n"
            "This usually happens when your map has breaking changes which void current votes.\n"
            f"{itx.message.jump_url}"
        )

    async def remove_votes_option(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            content="Are you sure you want to remove all the votes for this submission?",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return
        await self._unset_ready_button(itx, self.ready_up_button)
        await itx.message.channel.send(
            "@here, All votes have been removed by a Sensei."
        )
        await self.remove_votes()

    async def remove_completions_option(self, itx: discord.Interaction[core.Genji]):
        view = views.Confirm(itx)
        await itx.response.send_message(
            content="Are you sure you want to remove all the completions for this submission?",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return
        await self._unset_ready_button(itx, self.ready_up_button)
        await itx.message.channel.send(
            "@here, All records have been removed by a Sensei."
        )
        await self.remove_records()

    async def toggle_finalize_button(self, itx: discord.Interaction[core.Genji]):
        if await self.check_creator(itx):
            await itx.response.send_message(
                "You cannot use this if you are the creator.", ephemeral=True
            )
            return
        view = views.Confirm(itx)
        await itx.response.send_message(
            content="Are you sure you want to toggle the Finalize button for this submission?",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if not view.value:
            return

        self.ready_up_button.disabled = not self.ready_up_button.disabled
        await itx.message.edit(view=self)
        if not self.ready_up_button.disabled:
            await itx.channel.send(
                f"{self.data.creator.mention}, "
                f"the Finalize Submission button has been enabled by a Sensei."
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

    async def time_limit_deletion(self):
        self.stop()
        record = await self.get_author_db_row()
        await self.lock_and_archive_thread(record.thread_id)
        # await self.delete_playtest_post(record.thread_id)
        await self.delete_map_from_db()
        await self.delete_playtest_db_entry()
        self.client.cache.maps.remove_one(self.data.map_code)
