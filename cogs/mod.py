from __future__ import annotations

import json
import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

import views
from database import Database
from utils import constants, embeds, errors, map_submission, maps, ranks, transformers, utils
from utils.newsfeed import NewsfeedEvent
from views import GuidesSelect, Paginator

if typing.TYPE_CHECKING:
    import core
    from views.maps import PlaytestVoting


class ModCommands(commands.Cog):
    def __init__(self, bot: core.Genji) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context[core.Genji]) -> bool:
        return True

    mod = app_commands.Group(
        name="mod",
        guild_ids=[constants.GUILD_ID],
        description="Mod only commands",
    )
    map = app_commands.Group(
        name="map",
        guild_ids=[constants.GUILD_ID],
        description="Mod only commands",
        parent=mod,
    )

    @map.command(name="remove-guide")
    async def remove_guide(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        """Remove a guide from a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        query = "SELECT url FROM guides WHERE map_code = $1;"
        guides = [x.url async for x in itx.client.database.get(query, map_code)]
        if not guides:
            raise errors.NoGuidesExistError

        guides_formatted = [f"{utils.convert_to_emoji_number(i)}. <{g[:100]}>\n" for i, g in enumerate(guides, start=1)]

        content = (
            f"# Guides for {map_code}\n"
            f"### Select the corresponding number to delete the guide.\n"
            f"{''.join(guides_formatted)}\n"
        )

        options = [
            discord.SelectOption(label=utils.convert_to_emoji_number(x + 1), value=str(x)) for x in range(len(guides))
        ]
        select = GuidesSelect(options)
        view = views.Confirm(itx, proceeding_items={"guides": select}, ephemeral=True)

        await itx.edit_original_response(
            content=content,
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        url = guides[int(view.guides.values[0])]
        query = "DELETE FROM guides WHERE map_code = $1 AND url = $2;"
        await itx.client.database.set(query, map_code, url)
        await itx.edit_original_response(content=f"# Deleted guide\n## Map code: {map_code}\n## URL: {url}")

    @map.command(name="add-creator")
    async def add_creator(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        creator: app_commands.Transform[discord.Member | utils.FakeUser, transformers.AllUserTransformer],
    ) -> None:
        """Add a creator to a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User

        """
        await map_submission.add_creator_(creator.id, itx, map_code)

    @map.command(name="remove-creator")
    async def remove_creator(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        creator: app_commands.Transform[discord.Member | utils.FakeUser, transformers.AllUserTransformer],
    ) -> None:
        """Remove a creator from a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User

        """
        await map_submission.remove_creator_(creator.id, itx, map_code)

    @map.command(name="edit-medals")
    async def edit_medals(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        gold: app_commands.Transform[float, transformers.RecordTransformer],
        silver: app_commands.Transform[float, transformers.RecordTransformer],
        bronze: app_commands.Transform[float, transformers.RecordTransformer],
    ) -> None:
        """Edit all medals for a map. Set all medals to 0 to remove them.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            gold: Gold medal time
            silver: Silver medal time
            bronze: Bronze medal time

        """
        await itx.response.defer(ephemeral=True)
        delete = gold == silver == bronze == 0

        if not delete and not 0 < gold < silver < bronze:
            raise errors.InvalidMedalsError

        if delete:
            query = "DELETE FROM map_medals WHERE map_code = $1"
            args = (map_code,)
            content = f"{map_code} medals have been removed.\n"
        else:
            query = """
            INSERT INTO map_medals (gold, silver, bronze, map_code)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (map_code)
            DO UPDATE SET gold = $1, silver = $2, bronze = $3
            WHERE map_medals.map_code = EXCLUDED.map_code
            """
            args = (gold, silver, bronze, map_code)
            content = (
                f"{map_code} medals have been changed to:\n"
                f"`Gold` {gold}\n"
                f"`Silver` {silver}\n"
                f"`Bronze` {bronze}\n"
            )
        await itx.client.database.set(query, *args)
        await itx.edit_original_response(content=content)
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1 AND original_msg IS NOT NULL",
            map_code,
        ):
            await self._newsfeed_medals(
                itx,
                map_code,
                delete,
                gold,
                silver,
                bronze,
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            await self._newsfeed_medals(itx, map_code, delete, gold, silver, bronze)
            await utils.update_affected_users(itx.client, itx.guild, map_code)

    @staticmethod
    def _edit_medals(embed: discord.Embed, gold: float, silver: float, bronze: float) -> discord.Embed:
        medals_txt = (
            f"┣ `Medals` "
            f"{constants.FULLY_VERIFIED_GOLD} {gold} | "
            f"{constants.FULLY_VERIFIED_SILVER} {silver} | "
            f"{constants.FULLY_VERIFIED_BRONZE} {bronze}\n┗"
        )
        if bool(re.search("`Medals`", embed.description)):
            embed.description = re.sub(
                r"┣ `Medals` (.+)\n┗",
                medals_txt,
                embed.description,
            )
        else:
            embed.description = re.sub(
                r"┗",
                medals_txt,
                embed.description,
            )
        return embed

    async def _newsfeed_medals(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: str,
        delete: bool,
        gold: float,
        silver: float,
        bronze: float,
        thread_id: int | None = None,
        message_id: int | None = None,
    ) -> None:
        description = "All medals removed."
        if not delete:
            description = f"`Gold` {gold}\n" f"`Silver` {silver}\n" f"`Bronze` {bronze}\n"
        embed = embeds.GenjiEmbed(
            title=f"Medals have been added/changed for code {map_code}",
            description=description,
            color=discord.Color.red(),
        )

        if thread_id:
            await itx.guild.get_thread(thread_id).send(embed=embed)
            original = await itx.guild.get_channel(constants.PLAYTEST).fetch_message(message_id)
            embed = self._edit_medals(original.embeds[0], gold, silver, bronze)
            await original.edit(embed=embed)
        else:
            await itx.guild.get_channel(constants.NEWSFEED).send(embed=embed)

    @map.command(name="submit-map")
    async def submit_fake_map(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[utils.FakeUser | discord.Member, transformers.AllUserTransformer],
        map_code: app_commands.Transform[str, transformers.MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, transformers.MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, transformers.RecordTransformer] | None = None,
        silver: app_commands.Transform[float, transformers.RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, transformers.RecordTransformer] | None = None,
    ) -> None:
        """Submit a map for a specific user to the database This will skip the playtesting phase.

        Args:
            itx: Interaction
            user: user
            map_code: Overwatch share code
            map_name: Overwatch map
            checkpoint_count: Number of checkpoints in the map
            description: Other optional information for the map
            guide_url: Guide URL
            gold: Gold medal time (must be the fastest time)
            silver: Silver medal time (must be between gold and bronze)
            bronze: Bronze medal time (must be the slowest time)

        """
        medals = None
        if gold and silver and bronze:
            medals = (gold, silver, bronze)

        submission = maps.MapSubmission(
            creator=user,
            map_code=map_code,
            map_name=map_name,
            checkpoint_count=checkpoint_count,
            description=description,
            guides=[guide_url],
            medals=medals,
        )
        await map_submission.submit_map_(
            itx,
            submission,
            mod=True,
        )

    @mod.command(name="remove-record")
    async def remove_record(
        self,
        itx: discord.Interaction[core.Genji],
        member: discord.Member,
        map_code: app_commands.Transform[str, transformers.MapCodeRecordsTransformer],
    ) -> None:
        """Remove a record from the database/user.

        Args:
            itx: Interaction
            member: User
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        # TODO: Add multi record inserted_at dropdown to choose which to delete
        remove_query = """
            SELECT * FROM records r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.user_id = $1 AND map_code = $2
            ORDER BY inserted_at
            LIMIT 1;
        """

        record = await self.bot.database.fetchrow(remove_query, member.id, map_code)
        if not record:
            raise errors.NoRecordsFoundError

        embed = embeds.GenjiEmbed(
            title="Delete Record",
            description=(
                f"`Name` {discord.utils.escape_markdown(record['nickname'])}\n"
                f"`Code` {record['map_code']}\n"
                f"`Record` {record['record']}\n"
            ),
        )
        view = views.Confirm(itx)
        await itx.edit_original_response(content="Delete this record?", embed=embed, view=view)
        await view.wait()

        if not view.value:
            return

        await self.bot.database.set(
            "DELETE FROM records WHERE user_id = $1 AND map_code = $2 AND inserted_at = $3",
            member.id,
            map_code,
            record["inserted_at"],
        )

        await member.send(f"Your record for {map_code} has been deleted by staff.")
        await utils.auto_skill_role(itx.client, itx.guild, member)

    @mod.command(name="change-name")
    async def change_name(
        self,
        itx: discord.Interaction[core.Genji],
        member: app_commands.Transform[discord.Member | utils.FakeUser, transformers.AllUserTransformer],
        nickname: app_commands.Range[str, 1, 25],
    ) -> None:
        """Change a user display name.

        Args:
            itx: Interaction
            member: User
            nickname: New nickname

        """
        old = await self.bot.database.fetch_nickname(member.id)
        query = "UPDATE users SET nickname = $1 WHERE user_id = $2;"
        await self.bot.database.execute(query, nickname, member.id)
        await itx.response.send_message(
            f"Changing {old} ({member}) nickname to {nickname}",
            ephemeral=True,
        )

    @mod.command(name="create-fake-member")
    async def create_fake_member(
        self,
        itx: discord.Interaction[core.Genji],
        fake_user: str,
    ) -> None:
        """Create a fake user.

        MAKE SURE THIS USER DOESN'T ALREADY EXIST!

        Args:
            itx: Discord itx
            fake_user: The fake user

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(itx, ephemeral=True)
        await itx.edit_original_response(
            content=f"Create fake user {fake_user}?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return

        fake_user_id_query = "SELECT COALESCE(MAX(user_id) + 1, 1) FROM users WHERE user_id < 100000 LIMIT 1;"
        user_id = await self.bot.database.fetchval(fake_user_id_query)
        query = "INSERT INTO users (user_id, nickname) VALUES ($1, $2);"
        await itx.client.database.execute(query, user_id, fake_user)

    @mod.command(name="link-member")
    async def link_member(
        self,
        itx: discord.Interaction[core.Genji],
        fake_user: app_commands.Transform[utils.FakeUser, transformers.FakeUserTransformer],
        member: discord.Member,
    ) -> None:
        """Link a fake user to a server member.

        Args:
            itx: Discord itx
            fake_user: The fake user
            member: The real user

        """
        await itx.response.defer(ephemeral=True)
        try:
            _fake_user = int(fake_user)
        except ValueError:
            raise errors.InvalidFakeUserError

        fake_member_limit = 100000
        if _fake_user >= fake_member_limit:
            raise errors.InvalidFakeUserError
        fake_name = await itx.client.database.get_row("SELECT * FROM users WHERE user_id=$1", _fake_user)
        if not fake_name:
            raise errors.InvalidFakeUserError

        view = views.Confirm(itx, ephemeral=True)
        await itx.edit_original_response(
            content=f"Link {fake_name.nickname} to {member.mention}?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await self.link_fake_to_member(itx, _fake_user, member)

    @staticmethod
    async def link_fake_to_member(itx: discord.Interaction[core.Genji], fake_id: int, member: discord.Member) -> None:
        await itx.client.database.execute("UPDATE map_creators SET user_id=$2 WHERE user_id=$1", fake_id, member.id)
        await itx.client.database.execute("UPDATE map_ratings SET user_id=$2 WHERE user_id=$1", fake_id, member.id)
        await itx.client.database.execute("DELETE FROM users WHERE user_id=$1", fake_id)

    @mod.command(name="audit-log")
    async def audit_log(
        self,
        itx: discord.Interaction[core.Genji],
        limit: app_commands.Range[int, 1, 500] = 10,
        command_name: str | None = None,
    ) -> None:
        """View genjibot audit logs.

        Args:
            itx: Discord itx
            limit: Limit amount of audit log entries
            command_name: Limit to a specific command name

        """
        await itx.response.defer(ephemeral=True)
        query = """
            SELECT *
            FROM analytics
            WHERE $2::text IS NULL OR "event" = $2
            ORDER BY date_collected DESC
            LIMIT $1;
        """
        rows = await itx.client.database.fetch(query, limit, command_name)
        if not rows:
            raise errors.BaseParkourError("No audit log entries found")
        content = []
        for row in rows:
            command = row["event"]
            if command in ["sync", "audit-log"] or command.startswith("jsk"):
                continue
            timestamp = discord.utils.format_dt(row["date_collected"], style='F')
            assert itx.guild
            user = itx.guild.get_member(row["user_id"])
            mention = user.mention if user else row["user_id"]
            args = ""
            args_json = json.loads(row["args"])
            for k, v in args_json.items():
                args += f"> `{k}` {v}\n"
            content.append(f"{mention} used **{command}**\n{timestamp}\n{args}\n")
        chunks = discord.utils.as_chunks(content, 10)
        _embeds = [embeds.GenjiEmbed(title="Audit Log Entries", description="\n".join(chunk)) for chunk in chunks]
        if not _embeds:
            raise errors.BaseParkourError("No audit log entries found")
        view = Paginator(_embeds, itx.user)
        await view.start(itx)


    @map.command()
    @app_commands.choices(
        action=[
            app_commands.Choice(name="archive", value="archive"),
            app_commands.Choice(name="unarchive", value="unarchive"),
        ]
    )
    async def archive(
        self,
        itx: discord.Interaction[core.Genji],
        action: app_commands.Choice[str],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        await itx.response.defer(ephemeral=True)
        query = """
            WITH all_maps AS (
                SELECT
                    map_name,
                    m.map_code,
                    archived,
                    array_agg(DISTINCT nickname) AS creators,
                    coalesce(avg(difficulty), 0) AS difficulty
                FROM maps m
                LEFT JOIN map_creators mc ON m.map_code = mc.map_code
                LEFT JOIN users u ON mc.user_id = u.user_id
                LEFT JOIN map_ratings mr ON m.map_code = mr.map_code
                GROUP BY map_name, m.map_code, archived
            )
            SELECT am.map_name, am.map_code, am.archived, creators, difficulty
            FROM all_maps am
            LEFT JOIN playtest p ON am.map_code = p.map_code AND p.is_author IS TRUE
            WHERE am.map_code = $1
        """
        row = await itx.client.database.fetchrow(query, map_code)

        if not row:
            raise ValueError("Map wasn't found.")

        if action.value == "archive" and row["archived"] is False:
            value = True

        elif action.value == "unarchive" and row["archived"] is True:
            value = False

        else:
            await itx.edit_original_response(content=f"**{map_code}** has already been {action.value}d.")
            return

        await itx.client.database.set(
            """UPDATE maps SET archived = $1 WHERE map_code = $2""",
            value,
            map_code,
        )
        await itx.edit_original_response(content=f"**{map_code}** has been {action.value}d.")

        _data = {
            "map": {
                "map_code": row["map_code"],
                "creators": row["creators"],
                "difficulty": float(row["difficulty"]),
                "map_name": row["map_name"],
            }
        }
        event = NewsfeedEvent(action.value, _data)
        await itx.client.genji_dispatch.handle_event(event, itx.client)

    @map.command()
    @app_commands.choices(value=ranks.DIFFICULTIES_CHOICES)
    async def difficulty(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        value: app_commands.Choice[str],
    ) -> None:
        """Completely change the difficulty of a map.

        This will change all votes to the supplied value.

        Args:
            itx: Discord interaction
            map_code: Overwatch share code
            value: Difficulty

        """
        await itx.response.defer(ephemeral=True)
        difficulty = ranks.ALL_DIFFICULTY_RANGES_MIDPOINT[value.value]
        view = views.Confirm(itx, f"Updated {map_code} difficulty to {value.value}.", ephemeral=True)
        await itx.edit_original_response(
            content=f"{map_code} difficulty to {value.value}. Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            "UPDATE map_ratings SET difficulty=$1 WHERE map_code=$2",
            difficulty,
            map_code,
        )
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg, message_id FROM playtest WHERE map_code=$1",
            map_code,
        ):
            await itx.client.database.set(
                "UPDATE playtest SET value = $1 WHERE message_id = $2 AND is_author = TRUE",
                difficulty,
                playtest.message_id,
            )
            view = self.bot.playtest_views[playtest.message_id]
            cur_required_votes = view.required_votes
            view.change_difficulty(difficulty)
            new_required_votes = view.required_votes
            if cur_required_votes != new_required_votes:
                msg = await itx.guild.get_channel(constants.PLAYTEST).get_partial_message(playtest.thread_id).fetch()
                content, total_votes = await self._regex_replace_votes(msg, view)
                await msg.edit(content=content)
                await view.mod_check_status(int(total_votes), msg)

            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Difficulty": value.value},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            await utils.update_affected_users(itx.client, itx.guild, map_code)
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Difficulty": value.value})

    async def _regex_replace_votes(self, msg: discord.Message, view: PlaytestVoting) -> tuple[str, str]:
        regex = r"Total Votes: (\d+) / \d+"
        search = re.search(regex, msg.content)
        total_votes = search.group(1)
        content = re.sub(regex, f"Total Votes: {total_votes} / {view.required_votes}", msg.content)
        return content, total_votes

    @map.command()
    @app_commands.choices(value=constants.ALL_STARS_CHOICES)
    async def rating(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        value: app_commands.Choice[int],
    ) -> None:
        """Completely change the rating of a map.

        This will change all votes to the supplied value.

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            value: Rating number 1-6

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(itx, f"Updated {map_code} quality rating to {value}.", ephemeral=True)
        await itx.edit_original_response(
            content=f"{map_code} quality rating to {value}. Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            "UPDATE map_ratings SET quality=$1 WHERE map_code=$2",
            value,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} quality rating to {value}.")
        itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Quality": value.name})

    @map.command(name="map-type")
    async def map_type(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        """Change the type of map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        options = await utils.db_records_to_options(self.bot.database, "map_type")
        select = {"map_type": views.MapTypeSelect(options)}
        view = views.Confirm(itx, proceeding_items=select, ephemeral=True)
        await itx.edit_original_response(
            content="Select the new map type(s).",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        map_types = view.map_type.values
        await itx.client.database.execute(
            "UPDATE maps SET map_type=$1 WHERE map_code=$2",
            map_types,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} types to {', '.join(map_types)}.")
        # If playtesting
        if playtest := await itx.client.database.fetchrow(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Type": ", ".join(map_types)},
                playtest["thread_id"],
                playtest["original_msg"],
            )
        else:
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Type": ", ".join(map_types)},
            )

    async def _preload_map_select_menu(
        self, type_: typing.Literal["mechanics", "restrictions"], map_code: str
    ) -> list[str]:
        if type_ == "mechanics":
            query = "SELECT mechanic AS name FROM map_mechanics WHERE map_code = $1"
        elif type_ == "restrictions":
            query = ""
        else:
            raise ValueError("Unknown type.")
        rows = await self.bot.database.fetch(query, map_code)
        return [row["name"] for row in rows]

    @map.command()
    async def mechanics(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        """Change the mechanics of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        preload_options = await self._preload_map_select_menu("mechanics", map_code)
        options = await utils.db_records_to_options(self.bot.database, "mechanics")
        for option in options:
            option.default = option.value in preload_options

        select = {
            "mechanics": views.MechanicsSelect([*options, discord.SelectOption(label="Remove All", value="Remove All")])
        }
        view = views.Confirm(itx, proceeding_items=select, ephemeral=True)
        await itx.edit_original_response(
            content="Select the new map mechanic(s).",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        mechanics = view.mechanics.values
        await itx.client.database.execute("DELETE FROM map_mechanics WHERE map_code=$1", map_code)
        if "Remove All" not in mechanics:
            mechanics_args = [(map_code, x) for x in mechanics]
            await itx.client.database.executemany(
                "INSERT INTO map_mechanics (map_code, mechanic) VALUES ($1, $2)",
                mechanics_args,
            )
            mechanics = ", ".join(mechanics)
        else:
            mechanics = "Removed all mechanics"

        await itx.edit_original_response(content=f"Updated {map_code} mechanics: {mechanics}.")
        # If playtesting
        if playtest := await itx.client.database.fetchrow(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Mechanics": mechanics},
                playtest["thread_id"],
                playtest["original_msg"],
            )
        else:
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Mechanics": mechanics},
            )

    @map.command()
    async def restrictions(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        """Change the restrictions of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        preload_options = await self._preload_map_select_menu("restrictions", map_code)
        options = await utils.db_records_to_options(self.bot.database, "restrictions")
        for option in options:
            option.default = option.value in preload_options

        select = {
            "restrictions": views.RestrictionsSelect(
                [*options, discord.SelectOption(label="Remove All", value="Remove All")]
            )
        }
        view = views.Confirm(itx, proceeding_items=select, ephemeral=True)
        await itx.edit_original_response(
            content="Select the new map restrictions(s).",
            view=view,
        )
        await view.wait()
        if not view.value:
            return

        restrictions = view.restrictions.values

        await itx.client.database.execute("DELETE FROM map_restrictions WHERE map_code=$1", map_code)
        if "Remove All" not in restrictions:
            restrictions_args = [(map_code, x) for x in restrictions]
            await itx.client.database.executemany(
                "INSERT INTO map_restrictions (map_code, restriction) VALUES ($1, $2)",
                restrictions_args,
            )
            restrictions = ", ".join(restrictions)
        else:
            restrictions = "Removed all restrictions"

        await itx.edit_original_response(content=f"Updated {map_code} restrictions: {restrictions}.")
        # If playtesting
        if playtest := await itx.client.database.fetchrow(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Restrictions": restrictions},
                playtest["thread_id"],
                playtest["original_msg"],
            )
        else:
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Restrictions": restrictions},
            )

    @map.command()
    async def checkpoints(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
    ) -> None:
        """Change the checkpoint count of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            checkpoint_count: Number of checkpoints in the map

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(
            itx,
            f"Updated {map_code} checkpoint count to {checkpoint_count}.",
            ephemeral=True,
        )
        await itx.edit_original_response(
            content=f"{map_code} checkpoint count to {checkpoint_count}. Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            "UPDATE maps SET checkpoints=$1 WHERE map_code=$2",
            checkpoint_count,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} checkpoint count to {checkpoint_count}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Checkpoints": checkpoint_count},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Checkpoints": checkpoint_count})

    @map.command(name="map-code")
    async def map_code(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        new_map_code: app_commands.Transform[str, transformers.MapCodeSubmitTransformer],
    ) -> None:
        """Change the map code of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            new_map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        if await self.bot.database.is_existing_map_code(new_map_code):
            raise errors.MapExistsError

        view = views.Confirm(itx, f"Updated {map_code} map code to {new_map_code}.", ephemeral=True)
        await itx.edit_original_response(
            content=f"{map_code} map code to {new_map_code}. Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.execute(
            "UPDATE maps SET map_code = $1 WHERE map_code = $2",
            new_map_code,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} map code to {new_map_code}.")
        # If playtesting
        if playtest := await itx.client.database.fetchrow(
            "SELECT thread_id, original_msg, message_id FROM playtest WHERE map_code=$1",
            map_code,
        ):
            await itx.client.database.execute(
                "UPDATE playtest SET map_code=$1 WHERE map_code=$2",
                new_map_code,
                map_code,
            )

            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Code": new_map_code},
                playtest["thread_id"],
                playtest["original_msg"],
            )

            self.bot.playtest_views[playtest["message_id"]].data.map_code = new_map_code
        else:
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Code": new_map_code})

    @map.command()
    async def description(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        description: str,
    ) -> None:
        """Change the description of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            description: Other optional information for the map

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(itx, f"Updated {map_code} description to {description}.", ephemeral=True)
        await itx.edit_original_response(
            content=f"{map_code} description to \n\n{description}\n\n Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            'UPDATE maps SET "desc"=$1 WHERE map_code=$2',
            description,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} description to {description}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Desc": description},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Description": description})

    @map.command(name="map-name")
    async def map_name(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
        map_name: app_commands.Transform[str, transformers.MapNameTransformer],
    ) -> None:
        """Change the description of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            map_name: Overwatch map

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(itx, f"Updated {map_code} map name to {map_name}.", ephemeral=True)
        await itx.edit_original_response(
            content=f"{map_code} map name to {map_name}. Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            "UPDATE maps SET map_name=$1 WHERE map_code=$2",
            map_name,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} map name to {map_name}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Map": map_name},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Map": map_name})

    @map.command()
    async def convert_legacy(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, transformers.MapCodeTransformer],
    ) -> None:
        await itx.response.defer(ephemeral=True)

        if await self._check_if_queued(map_code):
            await itx.edit_original_response(
                content="A submission for this map is in the verification queue. "
                "Please verify/reject that prior to using this command."
            )
            return

        view = views.Confirm(itx)
        await itx.edit_original_response(
            content=f"# Are you sure you want to convert current records on {map_code} to legacy?\n"
            f"This will:\n"
            f"- Move records to `/legacy_completions`\n"
            f"- Convert all time records into _completions_\n"
            f"- Remove medal times set for the map\n\n",
            view=view,
        )
        await view.wait()
        if not view.value:
            return

        await self._convert_records_to_legacy_completions(itx.client.database, map_code)
        await self._remove_map_medal_entries(map_code)

        _data = {
            "map": {
                "map_code": map_code,
            }
        }
        event = NewsfeedEvent("legacy_record", _data)
        await itx.client.genji_dispatch.handle_event(event, itx.client)

    async def _check_if_queued(self, map_code: str) -> bool:
        query = "SELECT EXISTS (SELECT * FROM records WHERE map_code = $1 AND verified IS FALSE);"
        return await self.bot.database.fetchval(query, map_code)

    async def _remove_map_medal_entries(self, map_code: str) -> None:
        query = "DELETE FROM map_medals WHERE map_code = $1;"
        await self.bot.database.execute(query, map_code)

    @staticmethod
    async def _convert_records_to_legacy_completions(db: Database, map_code: str) -> None:
        query = """
            WITH all_records AS (
                SELECT
                    CASE
                        WHEN verified = TRUE AND record <= gold THEN 'Gold'
                        WHEN verified = TRUE AND record <= silver AND record > gold THEN 'Silver'
                        WHEN verified = TRUE AND record <= bronze AND record > silver THEN 'Bronze'
                        END AS legacy_medal,
                    r.map_code,
                    r.user_id,
                    r.inserted_at
                FROM records r
                LEFT JOIN map_medals mm ON r.map_code = mm.map_code
                WHERE r.map_code = $1 AND legacy IS FALSE
                ORDER BY record
            )
            UPDATE records
            SET
                completion = CASE
                    WHEN all_records.legacy_medal IS NULL THEN TRUE
                    ELSE FALSE
                END,
                legacy = TRUE,
                legacy_medal = all_records.legacy_medal
            FROM all_records
            WHERE
                records.map_code = all_records.map_code AND
                records.user_id = all_records.user_id AND
                records.inserted_at = all_records.inserted_at;
        """
        await db.execute(query, map_code)


async def setup(bot: core.Genji) -> None:
    """Add cog to bot."""
    await bot.add_cog(ModCommands(bot))
