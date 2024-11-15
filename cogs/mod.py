from __future__ import annotations

import copy
import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import views
from database import DotRecord
from utils import constants, records, errors, utils, embeds, maps, cache, ranks
from views import GuidesSelect

if typing.TYPE_CHECKING:
    import core


class ModCommands(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context[core.Genji]) -> bool:
        return True
        # return bool(ctx.author.get_role(utils.STAFF))

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
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def remove_guide(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ) -> None:
        """
        Remove a guide from a map.

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
        view = views.Confirm(itx, ephemeral=True, preceeding_items={"guides": select})

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
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
        creator=cogs.users_autocomplete,
    )
    async def add_creator(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        creator: app_commands.Transform[int, records.UserTransformer],
    ) -> None:
        """
        Add a creator to a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User
        """
        await cogs.add_creator_(creator, itx, map_code)

    @map.command(name="remove-creator")
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
        creator=cogs.users_autocomplete,
    )
    async def remove_creator(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        creator: app_commands.Transform[int, records.UserTransformer],
    ) -> None:
        """
        Remove a creator from a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User
        """
        await cogs.remove_creator_(creator, itx, map_code)

    @map.command(name="edit-medals")
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def edit_medals(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        gold: app_commands.Transform[float, records.RecordTransformer],
        silver: app_commands.Transform[float, records.RecordTransformer],
        bronze: app_commands.Transform[float, records.RecordTransformer],
    ) -> None:
        """
        Edit all medals for a map. Set all medals to 0 to remove them.

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
            raise errors.InvalidMedals

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
            await utils.update_affected_users(itx.client, map_code)

    @staticmethod
    def _edit_medals(embed: discord.Embed, gold, silver, bronze) -> discord.Embed:
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
    ):
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
    @app_commands.autocomplete(
        user=cogs.users_autocomplete,
        map_name=cogs.map_name_autocomplete,
    )
    async def submit_fake_map(
        self,
        itx: discord.Interaction[core.Genji],
        user: app_commands.Transform[utils.FakeUser | discord.Member, records.AllUserTransformer],
        map_code: app_commands.Transform[str, records.MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, maps.MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, records.RecordTransformer] | None = None,
        silver: app_commands.Transform[float, records.RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, records.RecordTransformer] | None = None,
    ) -> None:
        """
        Submit a map for a specific user to the database This will skip the playtesting phase.

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

        map_submission = maps.MapSubmission(
            creator=user,
            map_code=map_code,
            map_name=map_name,
            checkpoint_count=checkpoint_count,
            description=description,
            guides=[guide_url],
            medals=medals,
        )
        await cogs.submit_map_(
            itx,
            map_submission,
            mod=True,
        )

    @mod.command(name="remove-record")
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def remove_record(
        self,
        itx: discord.Interaction[core.Genji],
        member: discord.Member,
        map_code: app_commands.Transform[str, records.MapCodeRecordsTransformer],
    ):
        """
        Remove a record from the database/user

        Args:
            itx: Interaction
            member: User
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        record = [
            x
            async for x in self.bot.database.get(
                "SELECT * FROM records r "
                "LEFT JOIN users u on r.user_id = u.user_id "
                "WHERE r.user_id=$1 AND map_code=$2",
                member.id,
                map_code,
            )
        ]
        if not record:
            raise errors.NoRecordsFoundError

        record = record[0]
        embed = embeds.GenjiEmbed(
            title="Delete Record",
            description=(
                f"`Name` {discord.utils.escape_markdown(record.nickname)}\n"
                f"`Code` {record.map_code}\n"
                f"`Record` {record.record}\n"
                # f"`Level` {record.level_name}\n"
            ),
        )
        view = views.Confirm(itx)
        await itx.edit_original_response(content="Delete this record?", embed=embed, view=view)
        await view.wait()

        if not view.value:
            return

        await self.bot.database.set(
            "DELETE FROM records WHERE user_id=$1 AND map_code=$2",
            member.id,
            map_code,
        )

        await member.send(f"Your record for {map_code} has been deleted by staff.")
        await utils.auto_role(itx.client, member)

    @mod.command(name="change-name")
    @app_commands.autocomplete(member=cogs.users_autocomplete)
    async def change_name(
        self,
        itx: discord.Interaction[core.Genji],
        member: app_commands.Transform[int, records.UserTransformer],
        nickname: app_commands.Range[str, 1, 25],
    ):
        """
        Change a user display name.

        Args:
            itx: Interaction
            member: User
            nickname: New nickname
        """
        old = self.bot.cache.users[member].nickname
        self.bot.cache.users[member].update_nickname(nickname)
        await self.bot.database.set("UPDATE users SET nickname=$1 WHERE user_id=$2", nickname, member)
        await itx.response.send_message(
            f"Changing {old} ({member}) nickname to {nickname}",
            ephemeral=True,
        )

    @mod.command(name="create-fake-member")
    async def create_fake_member(
        self,
        itx: discord.Interaction[core.Genji],
        fake_user: str,
    ):
        """
        Create a fake user. MAKE SURE THIS USER DOESN'T ALREADY EXIST!

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
        value = (
            await itx.client.database.get_row(
                "SELECT COALESCE(MAX(user_id) + 1, 1) user_id_ FROM users " "WHERE user_id < 100000 LIMIT 1;"
            )
        ).user_id_
        await itx.client.database.set(
            "INSERT INTO users (user_id, nickname) VALUES ($1, $2);",
            value,
            fake_user,
        )
        itx.client.cache.users.add_one(
            cache.UserData(
                user_id=value,
                nickname=fake_user,
                flags=cache.SettingFlags.NONE,
                is_creator=True,
            )
        )

    @mod.command(name="link-member")
    @app_commands.autocomplete(fake_user=cogs.users_autocomplete)
    async def link_member(
        self,
        itx: discord.Interaction[core.Genji],
        fake_user: str,
        member: discord.Member,
    ):
        """
        Link a fake user to a server member.

        Args:
            itx: Discord itx
            fake_user: The fake user
            member: The real user
        """
        await itx.response.defer(ephemeral=True)
        try:
            fake_user = int(fake_user)
        except ValueError:
            raise errors.InvalidFakeUser
        if fake_user >= 100000:
            raise errors.InvalidFakeUser
        fake_name = await itx.client.database.get_row("SELECT * FROM users WHERE user_id=$1", fake_user)
        if not fake_name:
            raise errors.InvalidFakeUser

        view = views.Confirm(itx, ephemeral=True)
        await itx.edit_original_response(
            content=f"Link {fake_name.nickname} to {member.mention}?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await self.link_fake_to_member(itx, fake_user, member)

    @staticmethod
    async def link_fake_to_member(itx: discord.Interaction[core.Genji], fake_id: int, member: discord.Member):
        await itx.client.database.set("UPDATE map_creators SET user_id=$2 WHERE user_id=$1", fake_id, member.id)
        await itx.client.database.set("UPDATE map_ratings SET user_id=$2 WHERE user_id=$1", fake_id, member.id)
        await itx.client.database.set(
            "DELETE FROM users WHERE user_id=$1",
            fake_id,
        )
        itx.client.cache.users[fake_id].update_user_id(member.id)

    @map.command()
    @app_commands.choices(
        action=[
            app_commands.Choice(name="archive", value="archive"),
            app_commands.Choice(name="unarchive", value="unarchive"),
        ]
    )
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def archive(
        self,
        itx: discord.Interaction[core.Genji],
        action: app_commands.Choice[str],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ):
        await itx.response.defer(ephemeral=True)
        row = None
        if action.value == "archive" and itx.client.cache.maps[map_code].archived is False:
            value = True
            row = await itx.client.database.get_row(
                """
                  WITH
                all_maps AS (
                  SELECT
                    map_name,
                    array_to_string((map_type), ', ') AS map_type,
                    m.map_code,
                    "desc",
                    official,
                    archived,
                    array_agg(DISTINCT url) AS guide,
                    array_to_string(array_agg(DISTINCT mech.mechanic), ', ') AS mechanics,
                    array_to_string(array_agg(DISTINCT rest.restriction), ', ') AS restrictions,
                    checkpoints,
                    string_agg(DISTINCT (nickname), ', ') AS creators,
                    coalesce(avg(difficulty), 0) AS difficulty,
                    coalesce(avg(quality), 0) AS quality,
                    array_agg(DISTINCT mc.user_id) AS creator_ids,
                    gold,
                    silver,
                    bronze
                    FROM
                      maps m
                        LEFT JOIN map_mechanics mech ON mech.map_code = m.map_code
                        LEFT JOIN map_restrictions rest ON rest.map_code = m.map_code
                        LEFT JOIN map_creators mc ON m.map_code = mc.map_code
                        LEFT JOIN users u ON mc.user_id = u.user_id
                        LEFT JOIN map_ratings mr ON m.map_code = mr.map_code
                        LEFT JOIN guides g ON m.map_code = g.map_code
                        LEFT JOIN map_medals mm ON m.map_code = mm.map_code
                   GROUP BY
                     checkpoints, map_name,
                     m.map_code, "desc", official, map_type, gold, silver, bronze, archived
                )
            SELECT
              am.map_name, map_type, am.map_code, am."desc", am.official,
              am.archived, guide, mechanics, restrictions, am.checkpoints,
              creators, difficulty, quality, creator_ids, am.gold, am.silver,
              am.bronze
              FROM
                all_maps am
                  LEFT JOIN playtest p ON am.map_code = p.map_code AND p.is_author IS TRUE
             WHERE
               am.map_code = $1
            
             GROUP BY
               am.map_name, map_type, am.map_code, am."desc", am.official, am.archived, guide, mechanics,
               restrictions, am.checkpoints, creators, difficulty, quality, creator_ids, am.gold, am.silver,
               am.bronze
                """,
                map_code,
            )

        elif action.value == "unarchive" and itx.client.cache.maps[map_code].archived is True:
            value = False
        else:
            await itx.edit_original_response(content=f"**{map_code}** has already been {action.value}d.")
            return
        itx.client.cache.maps[map_code].update_archived(value)
        await itx.client.database.set(
            """UPDATE maps SET archived = $1 WHERE map_code = $2""",
            value,
            map_code,
        )
        await itx.edit_original_response(content=f"**{map_code}** has been {action.value}d.")
        itx.client.dispatch("newsfeed_archive", itx, map_code, action.value, row)

    @map.command()
    @app_commands.choices(value=ranks.DIFFICULTIES_CHOICES)
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def difficulty(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: str,
        value: app_commands.Choice[str],
    ):
        """Completely change the difficulty of a map.
        This will change all votes to the supplied value.

        Args:
            itx: Discord interaction
            map_code: Overwatch share code
            value: Difficulty

        """
        await itx.response.defer(ephemeral=True)
        difficulty = ranks.ALL_DIFFICULTY_RANGES_MIDPOINT[value.value]
        view = views.Confirm(
            itx,
            f"Updated {map_code} difficulty to {value.value}.",
            ephemeral=True,
        )
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
            await utils.update_affected_users(itx.client, map_code)
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Difficulty": value.value})

    async def _regex_replace_votes(self, msg, view):
        regex = r"Total Votes: (\d+) / \d+"
        search = re.search(regex, msg.content)
        total_votes = search.group(1)
        content = re.sub(regex, f"Total Votes: {total_votes} / {view.required_votes}", msg.content)
        return content, total_votes

    @map.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    @app_commands.choices(value=constants.ALL_STARS_CHOICES)
    async def rating(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        value: app_commands.Choice[int],
    ):
        """Completely change the rating of a map.
        This will change all votes to the supplied value.

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            value: Rating number 1-6

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(
            itx,
            f"Updated {map_code} rating to {value}.",
            ephemeral=True,
        )
        await itx.edit_original_response(
            content=f"{map_code} rating to {value}. Is this correct?",
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
        await itx.edit_original_response(content=f"Updated {map_code} rating to {value}.")
        itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Rating": value.name})

    @map.command(name="map-type")
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def map_type(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ):
        """Change the type of map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        select = {"map_type": views.MapTypeSelect(copy.deepcopy(itx.client.cache.map_types.options))}
        view = views.Confirm(itx, ephemeral=True, preceeding_items=select)
        await itx.edit_original_response(
            content=f"Select the new map type(s).",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        map_types = view.map_type.values
        await itx.client.database.set(
            "UPDATE maps SET map_type=$1 WHERE map_code=$2",
            map_types,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} types to {', '.join(map_types)}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Type": ", ".join(map_types)},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Type": ", ".join(map_types)},
            )

    @map.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def mechanics(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ):
        """Change the mechanics of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        preload_options = [
            row.mechanic
            async for row in itx.client.database.get(
                "SELECT mechanic FROM map_mechanics WHERE map_code = $1",
                map_code,
            )
        ]
        options = copy.deepcopy(itx.client.cache.map_mechanics.options)
        for option in options:
            option.default = option.value in preload_options

        select = {
            "mechanics": views.MechanicsSelect(options + [discord.SelectOption(label="Remove All", value="Remove All")])
        }
        view = views.Confirm(itx, ephemeral=True, preceeding_items=select)
        await itx.edit_original_response(
            content=f"Select the new map mechanic(s).",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        mechanics = view.mechanics.values
        await itx.client.database.set("DELETE FROM map_mechanics WHERE map_code=$1", map_code)
        if "Remove All" not in mechanics:
            mechanics_args = [(map_code, x) for x in mechanics]
            await itx.client.database.set_many(
                "INSERT INTO map_mechanics (map_code, mechanic) VALUES ($1, $2)",
                mechanics_args,
            )
            mechanics = ", ".join(mechanics)
        else:
            mechanics = "Removed all mechanics"

        await itx.edit_original_response(content=f"Updated {map_code} mechanics: {mechanics}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Mechanics": mechanics},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Mechanics": mechanics},
            )

    @map.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def restrictions(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ):
        """Change the restrictions of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        preload_options = [
            row.restriction
            async for row in itx.client.database.get(
                "SELECT restriction FROM map_restrictions WHERE map_code = $1",
                map_code,
            )
        ]
        options = copy.deepcopy(itx.client.cache.map_restrictions.options)
        for option in options:
            option.default = option.value in preload_options

        select = {
            "restrictions": views.RestrictionsSelect(
                options + [discord.SelectOption(label="Remove All", value="Remove All")]
            )
        }
        view = views.Confirm(itx, ephemeral=True, preceeding_items=select)
        await itx.edit_original_response(
            content=f"Select the new map restrictions(s).",
            view=view,
        )
        await view.wait()
        if not view.value:
            return

        restrictions = view.restrictions.values

        await itx.client.database.set("DELETE FROM map_restrictions WHERE map_code=$1", map_code)
        if "Remove All" not in restrictions:
            restrictions_args = [(map_code, x) for x in restrictions]
            await itx.client.database.set_many(
                "INSERT INTO map_restrictions (map_code, restriction) VALUES ($1, $2)",
                restrictions_args,
            )
            restrictions = ", ".join(restrictions)
        else:
            restrictions = "Removed all restrictions"

        await itx.edit_original_response(content=f"Updated {map_code} restrictions: {restrictions}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Restrictions": restrictions},
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Restrictions": restrictions},
            )

    @map.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def checkpoints(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
    ):
        """Change the checkpoint count of a map

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
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def map_code(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        new_map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ):
        """Change the map code of a map

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            new_map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        if new_map_code in itx.client.cache.maps.keys:
            raise errors.MapExistsError

        view = views.Confirm(
            itx,
            f"Updated {map_code} map code to {new_map_code}.",
            ephemeral=True,
        )
        await itx.edit_original_response(
            content=f"{map_code} map code to {new_map_code}. Is this correct?",
            view=view,
        )
        await view.wait()
        if not view.value:
            return
        await itx.client.database.set(
            "UPDATE maps SET map_code=$1 WHERE map_code=$2",
            new_map_code,
            map_code,
        )
        await itx.edit_original_response(content=f"Updated {map_code} map code to {new_map_code}.")
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg, message_id FROM playtest WHERE map_code=$1",
            map_code,
        ):
            await itx.client.database.set(
                "UPDATE playtest SET map_code=$1 WHERE map_code=$2",
                new_map_code,
                map_code,
            )

            itx.client.dispatch(
                "newsfeed_map_edit",
                itx,
                map_code,
                {"Code": new_map_code},
                playtest.thread_id,
                playtest.original_msg,
            )

            self.bot.playtest_views[playtest.message_id].data.map_code = new_map_code
        else:
            itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Code": new_map_code})
        itx.client.cache.maps[map_code].update_map_code(new_map_code)

    @map.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def description(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        description: str,
    ):
        """Change the description of a map

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            description: Other optional information for the map

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(
            itx,
            f"Updated {map_code} description to {description}.",
            ephemeral=True,
        )
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
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
        map_name=cogs.map_name_autocomplete,
    )
    async def map_name(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
        map_name: app_commands.Transform[str, maps.MapNameTransformer],
    ):
        """Change the description of a map

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            map_name: Overwatch map

        """
        await itx.response.defer(ephemeral=True)

        view = views.Confirm(
            itx,
            f"Updated {map_code} map name to {map_name}.",
            ephemeral=True,
        )
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
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def convert_legacy(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, records.MapCodeTransformer],
    ):
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
            f"- Move records with medals to `/legacy_completions`\n"
            f"- Convert all time records into _completions_\n"
            f"- Remove medals\n\n",
            view=view,
        )
        await view.wait()
        if not view.value:
            return

        _records = await self._get_legacy_medal_records(itx, map_code)
        record_tuples = self._format_legacy_records_for_insertion(_records)
        await self._insert_legacy_records(record_tuples)
        await self._update_records_to_completions(map_code)
        await self._remove_medal_entries(map_code)

        embed = embeds.GenjiEmbed(
            title=f"{map_code} has been changed:",
            description=(
                "# Records have been converted to completions due to breaking changes.\n"
                "- View records that received medals using the `/legacy_completions` command"
            ),
            color=discord.Color.red(),
        )
        await itx.guild.get_channel(constants.NEWSFEED).send(embed=embed)

    async def _check_if_queued(self, map_code: str):
        query = """SELECT EXISTS (SELECT * FROM records_queue WHERE map_code = $1)"""
        row = await self.bot.database.get_row(query, map_code)
        return row.exists

    async def _remove_medal_entries(self, map_code):
        query = """
            DELETE FROM map_medals WHERE map_code = $1
        """
        await self.bot.database.set(query, map_code)

    async def _update_records_to_completions(self, map_code: str):
        query = """
            UPDATE records 
            SET video = NULL, verified = FALSE, record = 99999999.99
            WHERE map_code = $1
        """
        await self.bot.database.set(query, map_code)

    async def _insert_legacy_records(self, _records: list[tuple]):
        query = """
            INSERT INTO legacy_records (map_code, user_id, record, screenshot, video, message_id, channel_id, medal) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
        """
        await self.bot.database.set_many(query, _records)

    @staticmethod
    def _format_legacy_records_for_insertion(_records: list[DotRecord]):
        res = []
        for record in _records:
            if record.gold:
                medal = "Gold"
            elif record.silver:
                medal = "Silver"
            else:
                medal = "Bronze"

            res.append(
                (
                    record.map_code,
                    record.user_id,
                    record.record,
                    record.screenshot,
                    record.video,
                    record.message_id,
                    record.channel_id,
                    medal,
                )
            )
        return res

    @staticmethod
    async def _get_legacy_medal_records(itx, map_code):
        query = """
            WITH all_records AS (
                SELECT 
                    verified = TRUE AND record <= gold                       AS gold,
                    verified = TRUE AND record <= silver AND record > gold   AS silver,
                    verified = TRUE AND record <= bronze AND record > silver AS bronze,
                    r.map_code,
                    user_id,
                    screenshot,
                    record,
                    video,
                    message_id,
                    channel_id
                FROM records r
                    LEFT JOIN map_medals mm ON r.map_code = mm.map_code
                WHERE r.map_code = $1
                ORDER BY record
            )
            SELECT * FROM all_records WHERE gold OR silver OR bronze
        """
        return [record async for record in itx.client.database.get(query, map_code)]


async def setup(bot: core.Genji):
    await bot.add_cog(ModCommands(bot))
