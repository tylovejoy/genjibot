from __future__ import annotations

import copy
import pkgutil
import typing

import discord
from discord import app_commands

import utils
import views

if typing.TYPE_CHECKING:
    import core

EXTENSIONS = [
    module.name for module in pkgutil.iter_modules(__path__, f"{__package__}.")
]


def case_ignore_compare(string1: str | None, string2: str | None) -> bool:
    """
    Compare two strings, case-insensitive.
    Args:
        string1 (str): String 1 to compare
        string2 (str): String 2 to compare
    Returns:
        True if string2 is in string1
    """
    if None in [string1, string2]:
        return False
    return string2.casefold() in string1.casefold()


async def _autocomplete(
    current: str,
    choices: list[app_commands.Choice],
) -> list[app_commands.Choice[str]]:
    if not choices:  # Quietly ignore empty choices
        return []
    if current == "":
        response = choices[:25]
    else:
        response = [x for x in choices if case_ignore_compare(x.name, current)][:25]
    return response


async def creator_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.creators_choices)


# async def fake_users_autocomplete(
#     itx: core.Interaction[core.Genji], current: str
# ) -> list[app_commands.Choice[str]]:
#     return await _autocomplete(current, itx.client.fake_users_choices)


async def map_codes_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    current = current.replace("O", "0").replace("o", "0")
    return await _autocomplete(current, itx.client.map_codes_choices)


async def map_name_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.map_names_choices)


async def map_type_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.map_types_choices)


async def map_mechanics_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.map_mechanics_choices)


async def tags_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.tag_choices)


async def users_autocomplete(
    itx: core.Interaction[core.Genji], current: str
) -> list[app_commands.Choice[str]]:
    return await _autocomplete(current, itx.client.users_choices)


async def submit_map_(
    itx: core.Interaction[core.Genji],
    user: discord.Member | utils.FakeUser,
    map_code: str,
    map_name: str,
    checkpoint_count: int,
    description: str | None = None,
    guide_url: str | None = None,
    medals: tuple[float, float, float] | None = None,
    mod: bool = False,
) -> None:
    """
    Submit your map to the database.

    Args:
        itx: Interaction
        user: user
        map_code: Overwatch share code
        map_name: Overwatch map
        checkpoint_count: Number of checkpoints in the map
        description: Other optional information for the map
        guide_url: Guide URL
        medals: Gold, silver, bronze medal times
        mod: Mod command
    """

    await itx.response.defer(ephemeral=True)
    if not mod:
        diffs = utils.allowed_difficulties(
            await utils.Roles.find_highest_rank(itx.user)
        )

        if "Hard" not in diffs:
            raise utils.RankTooLowError
    else:
        diffs = utils.allowed_difficulties(7)
    if medals:
        if not 0 < medals[0] < medals[1] < medals[2]:
            raise utils.InvalidMedals

    view = views.Confirm(
        itx,
        preceeding_items={
            "map_type": views.MapTypeSelect(
                copy.deepcopy(itx.client.map_types_options)
            ),
            "mechanics": views.MechanicsSelect(
                copy.deepcopy(itx.client.map_mechanics_options)
            ),
            "restrictions": views.RestrictionsSelect(
                copy.deepcopy(itx.client.map_restrictions_options)
            ),
            "difficulty": views.DifficultySelect(
                [discord.SelectOption(label=x, value=x) for x in diffs]
            ),
        },
        ephemeral=True,
    )
    await itx.edit_original_response(
        content=(
            f"{user.mention}, "
            f"fill in additional details to complete map submission!"
        ),
        view=view,
    )
    await view.wait()
    if not view.value:
        return

    map_types = view.map_type.values
    mechanics = view.mechanics.values
    restrictions = view.restrictions.values
    difficulty = view.difficulty.values[0]
    guide_txt = ""
    medals_txt = ""
    if guide_url:
        guide_txt = f"┣ `Guide` [Link]({guide_url})\n"
    if medals and medals[0] is not None:
        gold, silver, bronze = medals
        medals_txt = (
            f"┣ `Medals` "
            f"{utils.FULLY_VERIFIED_GOLD} {gold} | "
            f"{utils.FULLY_VERIFIED_SILVER} {silver} | "
            f"{utils.FULLY_VERIFIED_BRONZE} {bronze}\n"
        )
    embed = utils.GenjiEmbed(
        title="Map Submission",
        description=(
            f"┣ `Code` {map_code}\n"
            f"┣ `Map` {map_name}\n"
            f"┣ `Type` {', '.join(map_types)}\n"
            f"┣ `Checkpoints` {checkpoint_count}\n"
            f"┣ `Difficulty` {difficulty}\n"
            f"┣ `Mechanics` {', '.join(mechanics)}\n"
            f"┣ `Restrictions` {', '.join(restrictions)}\n"
            f"{guide_txt}"
            f"{medals_txt}"
            f"┗ `Desc` {description}\n"
        ),
    )
    embed.set_author(
        name=itx.client.all_users[user.id]["nickname"],
        icon_url=user.display_avatar.url,
    )
    embed = utils.set_embed_thumbnail_maps(map_name, embed)
    view_confirm = views.Confirm(view.original_itx, ephemeral=True)
    await view_confirm.original_itx.edit_original_response(
        content=f"{itx.user.mention}, is this correct?",
        embed=embed,
        view=view_confirm,
    )
    await view_confirm.wait()
    if not view_confirm.value:
        return

    if not mod:
        embed.title = "Calling all Playtesters!"
        new_map = await itx.guild.get_channel(utils.PLAYTEST).send(embed=embed)
        embed = utils.GenjiEmbed(
            title="Difficulty Ratings",
            description="You can change your vote, but you cannot cast multiple!\n\n",
        )
        thread = await new_map.create_thread(name=f"Discuss/rate {map_code} here.")

        thread_msg = await thread.send(
            f"{itx.guild.get_role(utils.PLAYTESTER).mention}",
            view=views.PlaytestVoting(
                map_code,
                difficulty,
                itx.user.id,
                itx.client,
                new_map.id,
                await utils.Roles.find_highest_rank(itx.user),
            ),
            embed=embed,
        )

        await itx.client.database.set(
            """
            INSERT INTO playtest (thread_id, message_id, map_code, user_id, value, is_author, original_msg)
            VALUES ($1, $2, $3, $4, $5, $6, $7) 
            """,
            thread.id,
            thread_msg.id,
            map_code,
            itx.user.id,
            utils.DIFFICULTIES_RANGES[difficulty][0],
            True,
            new_map.id,
        )

    await itx.client.database.set(
        """
        INSERT INTO 
        maps (map_name, map_type, map_code, "desc", official, checkpoints) 
        VALUES ($1, $2, $3, $4, $5, $6);
        """,
        map_name,
        map_types,
        map_code,
        description,
        mod,
        checkpoint_count,
    )
    mechanics = [(map_code, x) for x in mechanics]
    await itx.client.database.set_many(
        """
        INSERT INTO map_mechanics (map_code, mechanic) VALUES ($1, $2);
        """,
        mechanics,
    )
    restrictions = [(map_code, x) for x in restrictions]
    await itx.client.database.set_many(
        """
        INSERT INTO map_restrictions (map_code, restriction) VALUES ($1, $2);
        """,
        restrictions,
    )
    await itx.client.database.set(
        """
        INSERT INTO map_creators (map_code, user_id) VALUES ($1, $2);
        """,
        map_code,
        user.id,
    )
    await itx.client.database.set(
        """
        INSERT INTO map_ratings (map_code, user_id, difficulty) VALUES ($1, $2, $3);
        """,
        map_code,
        user.id,
        utils.DIFFICULTIES_RANGES[difficulty][0],
    )
    if guide_url:
        await itx.client.database.set(
            """INSERT INTO guides (map_code, url) VALUES ($1, $2);""",
            map_code,
            guide_url,
        )

    if medals:
        await itx.client.database.set(
            """
            INSERT INTO map_medals (gold, silver, bronze, map_code)
            VALUES ($1, $2, $3, $4);
            """,
            medals[0],
            medals[1],
            medals[2],
            map_code,
        )

    itx.client.map_cache[map_code] = utils.MapCacheData(
        user_ids=[user.id],
        archived=False,
    )
    itx.client.map_codes_choices.append(
        app_commands.Choice(name=map_code, value=map_code)
    )
    if not mod:
        map_maker = itx.guild.get_role(utils.Roles.MAP_MAKER)
        if map_maker not in itx.user.roles:
            await itx.user.add_roles(map_maker, reason="Submitted a map.")
    else:
        embed.title = "New Map!"
        embed.set_footer(
            text="For notification of newly added maps only. "
                 "Data may be out of date. "
                 "Use the /map-search command for the latest info."
        )
        new_map_message = await itx.guild.get_channel(utils.NEW_MAPS).send(embed=embed)
        itx.client.dispatch(
            "newsfeed_new_map", itx, itx.user, new_map_message.jump_url, map_code
        )
    if user.id not in itx.client.creators:
        itx.client.creators[user.id] = itx.client.all_users[user.id]


async def add_creator_(creator, itx, map_code, checks: bool = False):
    await itx.response.defer(ephemeral=True)
    if not checks or itx.user.id not in itx.client.map_cache[map_code]["user_ids"]:
        raise utils.NoPermissionsError
    if creator in itx.client.map_cache[map_code]["user_ids"]:
        raise utils.CreatorAlreadyExists
    await itx.client.database.set(
        "INSERT INTO map_creators (map_code, user_id) VALUES ($1, $2)",
        map_code,
        creator,
    )
    itx.client.map_cache[map_code]["user_ids"].append(creator)
    await itx.edit_original_response(
        content=(
            f"Adding **{itx.client.all_users[creator]['nickname']}** "
            f"to list of creators for map code **{map_code}**."
        )
    )


async def remove_creator_(creator, itx, map_code, checks: bool = False):
    await itx.response.defer(ephemeral=True)
    if not checks or itx.user.id not in itx.client.map_cache[map_code]["user_ids"]:
        raise utils.NoPermissionsError
    if creator not in itx.client.map_cache[map_code]["user_ids"]:
        raise utils.CreatorDoesntExist
    await itx.client.database.set(
        "DELETE FROM map_creators WHERE map_code = $1 AND user_id = $2;",
        map_code,
        creator,
    )
    itx.client.map_cache[map_code]["user_ids"].remove(creator)
    await itx.edit_original_response(
        content=(
            f"Removing **{itx.client.all_users[creator]['nickname']}** "
            f"from list of creators for map code **{map_code}**."
        )
    )
