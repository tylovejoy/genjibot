from __future__ import annotations

import copy
import re
import typing

import discord
from discord import app_commands
from discord.ext import commands

import utils
import views
from cogs.maps.utils.utils import MapNameTransformer
from utils.autocomplete import (
    map_codes_autocomplete,
    users_autocomplete,
    map_name_autocomplete,
)

from utils import NEWSFEED

if typing.TYPE_CHECKING:
    import core
    from database import DotRecord


class MapEdits(commands.Cog):
    def __init__(self, bot: core.Genji):
        self.bot = bot

    @app_commands.command(name="add-creator")
    @app_commands.autocomplete(
        map_code=map_codes_autocomplete,
        creator=users_autocomplete,
    )
    async def add_creator(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        creator: app_commands.Transform[int, utils.UserTransformer],
    ) -> None:
        """
        Add a creator to a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User
        """
        await itx.response.defer(ephemeral=True)
        if creator in itx.client.cache.maps[map_code].user_ids:
            raise utils.CreatorAlreadyExists
        await itx.client.database.set(
            "INSERT INTO map_creators (map_code, user_id) VALUES ($1, $2)",
            map_code,
            creator,
        )
        itx.client.cache.maps[map_code].add_creator(creator)
        itx.client.cache.users[creator].is_creator = True
        await itx.edit_original_response(
            content=(
                f"Adding **{itx.client.cache.users[creator].nickname}** "
                f"to list of creators for map code **{map_code}**."
            )
        )

    @app_commands.command(name="remove-creator")
    @app_commands.autocomplete(
        map_code=map_codes_autocomplete,
        creator=users_autocomplete,
    )
    async def remove_creator(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        creator: app_commands.Transform[int, utils.UserTransformer],
    ) -> None:
        """
        Remove a creator from a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User
        """
        await itx.response.defer(ephemeral=True)
        if creator not in itx.client.cache.maps[map_code].user_ids:
            raise utils.CreatorDoesntExist
        await itx.client.database.set(
            "DELETE FROM map_creators WHERE map_code = $1 AND user_id = $2;",
            map_code,
            creator,
        )
        itx.client.cache.maps[map_code].remove_creator(creator)
        await itx.edit_original_response(
            content=(
                f"Removing **{itx.client.cache.users[creator].nickname}** "
                f"from list of creators for map code **{map_code}**."
            )
        )

    @app_commands.command(name="edit-medals")
    @app_commands.autocomplete(
        map_code=map_codes_autocomplete,
    )
    async def edit_medals(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        gold: app_commands.Transform[float, utils.RecordTransformer],
        silver: app_commands.Transform[float, utils.RecordTransformer],
        bronze: app_commands.Transform[float, utils.RecordTransformer],
    ) -> None:
        """
        Edit all medals for a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            gold: Gold medal time
            silver: Silver medal time
            bronze: Bronze medal time
        """

        await itx.response.defer(ephemeral=True)
        if not 0 < gold < silver < bronze:
            raise utils.InvalidMedals
        await itx.client.database.set(
            """            
            INSERT INTO map_medals (gold, silver, bronze, map_code)
            VALUES ($1, $2, $3, $4) 
            ON CONFLICT (map_code)
            DO UPDATE SET gold = $1, silver = $2, bronze = $3
            WHERE map_medals.map_code = excluded.map_code
            """,
            gold,
            silver,
            bronze,
            map_code,
        )
        await itx.edit_original_response(
            content=f"{map_code} medals have been changed to:\n"
            f"`Gold` {gold}\n"
            f"`Silver` {silver}\n"
            f"`Bronze` {bronze}\n"
        )
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
        ):
            itx.client.dispatch(
                "newsfeed_medals",
                itx,
                map_code,
                gold,
                silver,
                bronze,
                playtest.thread_id,
                playtest.original_msg,
            )
        else:
            itx.client.dispatch("newsfeed_medals", itx, map_code, gold, silver, bronze)
            await utils.update_affected_users(itx.client, map_code)

    @app_commands.command()
    @app_commands.choices(
        action=[
            app_commands.Choice(name="archive", value="archive"),
            app_commands.Choice(name="unarchive", value="unarchive"),
        ]
    )
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def archive(
        self,
        itx: discord.Interaction[core.Genji],
        action: app_commands.Choice[str],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        await itx.response.defer(ephemeral=True)
        row = None
        if (
            action.value == "archive"
            and itx.client.cache.maps[map_code].archived is False
        ):
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

        elif (
            action.value == "unarchive"
            and itx.client.cache.maps[map_code].archived is True
        ):
            value = False
        else:
            await itx.edit_original_response(
                content=f"**{map_code}** has already been {action.value}d."
            )
            return
        itx.client.cache.maps[map_code].update_archived(value)
        await itx.client.database.set(
            """UPDATE maps SET archived = $1 WHERE map_code = $2""",
            value,
            map_code,
        )
        await itx.edit_original_response(
            content=f"**{map_code}** has been {action.value}d."
        )
        itx.client.dispatch("newsfeed_archive", itx, map_code, action.value, row)

    @app_commands.command()
    @app_commands.choices(value=utils.DIFFICULTIES_CHOICES)
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
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
        difficulty = utils.DIFFICULTIES_RANGES[value.value][0]
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
                msg = (
                    await itx.guild.get_channel(utils.PLAYTEST)
                    .get_partial_message(playtest.thread_id)
                    .fetch()
                )
                content, _ = await self._regex_replace_votes(msg, view)
                await msg.edit(content=content)
                msg = (
                    await itx.guild.get_thread(playtest.thread_id)
                    .get_partial_message(playtest.message_id)
                    .fetch()
                )
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
            itx.client.dispatch(
                "newsfeed_map_edit", itx, map_code, {"Difficulty": value.value}
            )

    async def _regex_replace_votes(self, msg, view):
        regex = r"Total Votes: (\d+) / \d+"
        search = re.search(regex, msg.content)
        total_votes = search.group(1)
        content = re.sub(
            regex, f"Total Votes: {total_votes} / {view.required_votes}", msg.content
        )
        return content, total_votes

    @app_commands.command()
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    @app_commands.choices(value=utils.ALL_STARS_CHOICES)
    async def rating(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
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
        await itx.edit_original_response(
            content=f"Updated {map_code} rating to {value}."
        )
        itx.client.dispatch("newsfeed_map_edit", itx, map_code, {"Rating": value.name})

    @app_commands.command(name="map-type")
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def map_type(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        """Change the type of map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        select = {
            "map_type": views.MapTypeSelect(
                copy.deepcopy(itx.client.cache.map_types.options)
            )
        }
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
        await itx.edit_original_response(
            content=f"Updated {map_code} types to {', '.join(map_types)}."
        )
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

    @app_commands.command()
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def mechanics(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        """Change the mechanics of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        select = {
            "mechanics": views.MechanicsSelect(
                copy.deepcopy(itx.client.cache.map_mechanics.options)
                + [discord.SelectOption(label="Remove All", value="Remove All")]
            )
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
        await itx.client.database.set(
            "DELETE FROM map_mechanics WHERE map_code=$1", map_code
        )
        if "Remove All" not in mechanics:
            mechanics_args = [(map_code, x) for x in mechanics]
            await itx.client.database.set_many(
                "INSERT INTO map_mechanics (map_code, mechanic) VALUES ($1, $2)",
                mechanics_args,
            )
            mechanics = ", ".join(mechanics)
        else:
            mechanics = "Removed all mechanics"

        await itx.edit_original_response(
            content=f"Updated {map_code} mechanics: {mechanics}."
        )
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

    @app_commands.command()
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def restrictions(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        """Change the restrictions of a map.

        Args:
            itx: Discord itx
            map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)

        select = {
            "restrictions": views.RestrictionsSelect(
                copy.deepcopy(itx.client.cache.map_restrictions.options)
                + [discord.SelectOption(label="Remove All", value="Remove All")]
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

        await itx.client.database.set(
            "DELETE FROM map_restrictions WHERE map_code=$1", map_code
        )
        if "Remove All" not in restrictions:
            restrictions_args = [(map_code, x) for x in restrictions]
            await itx.client.database.set_many(
                "INSERT INTO map_restrictions (map_code, restriction) VALUES ($1, $2)",
                restrictions_args,
            )
            restrictions = ", ".join(restrictions)
        else:
            restrictions = "Removed all restrictions"

        await itx.edit_original_response(
            content=f"Updated {map_code} restrictions: {restrictions}."
        )
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

    @app_commands.command()
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def checkpoints(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
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
        await itx.edit_original_response(
            content=f"Updated {map_code} checkpoint count to {checkpoint_count}."
        )
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
            itx.client.dispatch(
                "newsfeed_map_edit", itx, map_code, {"Checkpoints": checkpoint_count}
            )

    @app_commands.command(name="map-code")
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def map_code(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        new_map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        """Change the map code of a map

        Args:
            itx: Discord itx
            map_code: Overwatch share code
            new_map_code: Overwatch share code

        """
        await itx.response.defer(ephemeral=True)
        if new_map_code in itx.client.cache.maps.keys:
            raise utils.MapExistsError

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
        await itx.edit_original_response(
            content=f"Updated {map_code} map code to {new_map_code}."
        )
        # If playtesting
        if playtest := await itx.client.database.get_row(
            "SELECT thread_id, original_msg FROM playtest WHERE map_code=$1", map_code
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
        else:
            itx.client.dispatch(
                "newsfeed_map_edit", itx, map_code, {"Code": new_map_code}
            )
        itx.client.cache.maps[map_code].update_map_code(new_map_code)

    @app_commands.command()
    @app_commands.autocomplete(map_code=map_codes_autocomplete)
    async def description(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
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
        await itx.edit_original_response(
            content=f"Updated {map_code} description to {description}."
        )
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
            itx.client.dispatch(
                "newsfeed_map_edit", itx, map_code, {"Description": description}
            )

    @app_commands.command(name="map-name")
    @app_commands.autocomplete(
        map_code=map_codes_autocomplete,
        map_name=map_name_autocomplete,
    )
    async def map_name(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        map_name: app_commands.Transform[str, MapNameTransformer],
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
        await itx.edit_original_response(
            content=f"Updated {map_code} map name to {map_name}."
        )
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

    @app_commands.command()
    @app_commands.autocomplete(
        map_code=map_codes_autocomplete,
    )
    async def convert_legacy(
        self,
        itx: discord.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
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

        records = await self._get_legacy_medal_records(itx, map_code)
        record_tuples = self._format_legacy_records_for_insertion(records)
        await self._insert_legacy_records(record_tuples)
        await self._update_records_to_completions(map_code)
        await self._remove_medal_entries(map_code)

        embed = utils.GenjiEmbed(
            title=f"{map_code} has been changed:",
            description=(
                "# Records have been converted to completions due to breaking changes.\n"
                "- View records that received medals using the `/legacy_completions` command"
            ),
            color=discord.Color.red(),
        )
        await itx.guild.get_channel(NEWSFEED).send(embed=embed)

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

    async def _insert_legacy_records(self, records: list[tuple]):
        query = """
                INSERT INTO legacy_records (map_code, user_id, record, screenshot, video, message_id, channel_id, medal) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
            """
        await self.bot.database.set_many(query, records)

    @staticmethod
    def _format_legacy_records_for_insertion(records: list[DotRecord]):
        res = []
        for record in records:
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
