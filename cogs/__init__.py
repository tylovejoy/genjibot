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
    data: utils.MapSubmission,
    mod: bool = False,
) -> None:
    """
    Submit your map to the database.

    Args:
        itx: Interaction
        data: MapSubmission obj
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

    data.creator_diffs = diffs

    if data.medals:
        if not 0 < data.gold < data.silver < data.bronze:
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
            f"{data.creator.mention}, "
            f"fill in additional details to complete map submission!"
        ),
        view=view,
    )
    await view.wait()
    if not view.value:
        return

    data.set_extras(
        map_types=view.map_type.values,
        mechanics=view.mechanics.values,
        restrictions=view.restrictions.values,
        difficulty=view.difficulty.values[0],
    )

    embed = utils.GenjiEmbed(
        title="Map Submission",
        description=str(data),
    )
    embed.set_author(
        name=itx.client.all_users[data.creator.id]["nickname"],
        icon_url=data.creator.display_avatar.url,
    )
    embed = utils.set_embed_thumbnail_maps(data.map_name, embed)

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
        playtest_message = await itx.guild.get_channel(utils.PLAYTEST).send(embed=embed)
        embed = utils.GenjiEmbed(
            title="Difficulty Ratings",
            description="You can change your vote, but you cannot cast multiple!\n\n",
        )
        thread = await playtest_message.create_thread(
            name=f"Discuss/rate {data.map_code} here."
        )

        thread_msg = await thread.send(
            f"Discuss, play, rate, etc.",
            view=views.PlaytestVoting(
                data,
                itx.client,
                playtest_message.id,
            ),
            embed=embed,
        )

        await data.insert_playtest(itx, thread.id, thread_msg.id, playtest_message.id)

    await data.insert_all(itx, mod)
    # ////////                    \\\\\\\\
    # Everything below this is cache stuff
    # \\\\\\\\                    ////////
    itx.client.map_cache[data.map_code] = utils.MapCacheData(
        user_ids=[data.creator.id],
        archived=False,
    )
    itx.client.map_codes_choices.append(
        app_commands.Choice(name=data.map_code, value=data.map_code)
    )
    if not mod:
        map_maker = itx.guild.get_role(utils.Roles.MAP_MAKER)
        if map_maker not in itx.user.roles:
            await itx.user.add_roles(map_maker, reason="Submitted a map.")
    else:
        embed.title = "New Map!"
        embed.set_footer(
            text=(
                "For notification of newly added maps only. "
                "Data may be wrong or out of date. "
                "Use the /map-search command for the latest info."
            )
        )
        new_map_message = await itx.guild.get_channel(utils.NEW_MAPS).send(embed=embed)
        itx.client.dispatch(
            "newsfeed_new_map", itx, itx.user, new_map_message.jump_url, data.map_code
        )
    if data.creator.id not in itx.client.creators:
        itx.client.creators[data.creator.id] = itx.client.all_users[data.creator.id]


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
