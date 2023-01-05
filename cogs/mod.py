from __future__ import annotations

import typing

import discord
from discord import app_commands
from discord.ext import commands

import cogs
import utils
import utils.maps
import views

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
        guild_ids=[utils.GUILD_ID],
        description="Mod only commands",
    )
    map = app_commands.Group(
        name="map",
        guild_ids=[utils.GUILD_ID],
        description="Mod only commands",
        parent=mod,
    )

    @map.command(name="add-creator")
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
        creator=cogs.users_autocomplete,
    )
    async def add_creator(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        creator: app_commands.Transform[int, utils.CreatorTransformer],
    ) -> None:
        """
        Add a creator to a map.

        Args:
            itx: Interaction
            map_code: Overwatch share code
            creator: User
        """
        await cogs.add_creator_(creator, itx, map_code, checks=True)

    @map.command(name="remove-creator")
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
        creator=cogs.users_autocomplete,
    )
    async def remove_creator(
        self,
        itx: core.Interaction[core.Genji],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
        creator: app_commands.Transform[int, utils.CreatorTransformer],
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
        itx: core.Interaction[core.Genji],
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
            WHERE map_medals.map_code = EXCLUDED.map_code
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
        itx.client.dispatch("newsfeed_medals", itx, map_code, gold, silver, bronze)
        await utils.update_affected_users(itx, map_code)

    @map.command(name="submit-map")
    @app_commands.autocomplete(
        user=cogs.users_autocomplete,
        map_name=cogs.map_name_autocomplete,
    )
    async def submit_fake_map(
        self,
        itx: core.Interaction[core.Genji],
        user: app_commands.Transform[
            utils.FakeUser | discord.Member, utils.AllUserTranformer
        ],
        map_code: app_commands.Transform[str, utils.MapCodeSubmitTransformer],
        map_name: app_commands.Transform[str, utils.MapNameTransformer],
        checkpoint_count: app_commands.Range[int, 1, 500],
        description: str | None = None,
        guide_url: str | None = None,
        gold: app_commands.Transform[float, utils.RecordTransformer] | None = None,
        silver: app_commands.Transform[float, utils.RecordTransformer] | None = None,
        bronze: app_commands.Transform[float, utils.RecordTransformer] | None = None,
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

        await cogs.submit_map_(
            itx,
            user,
            map_code,
            map_name,
            checkpoint_count,
            description,
            guide_url,
            medals,
            mod=True,
        )

    @mod.command(name="remove-record")
    @app_commands.autocomplete(
        map_code=cogs.map_codes_autocomplete,
    )
    async def remove_record(
        self,
        itx: core.Interaction[core.Genji],
        member: discord.Member,
        map_code: app_commands.Transform[str, utils.MapCodeRecordsTransformer],
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
            raise utils.NoRecordsFoundError

        record = record[0]
        embed = utils.GenjiEmbed(
            title="Delete Record",
            description=(
                f"`Name` {record.nickname}\n"
                f"`Code` {record.map_code}\n"
                f"`Record` {record.record}\n"
                # f"`Level` {record.level_name}\n"
            ),
        )
        view = views.Confirm(itx)
        await itx.edit_original_response(
            content="Delete this record?", embed=embed, view=view
        )
        await view.wait()

        if not view.value:
            return

        await self.bot.database.set(
            "DELETE FROM records WHERE user_id=$1 AND map_code=$2",
            member.id,
            map_code,
        )

    @mod.command(name="change-name")
    @app_commands.autocomplete(member=cogs.users_autocomplete)
    async def change_name(
        self,
        itx: core.Interaction[core.Genji],
        member: app_commands.Transform[int, utils.UserTransformer],
        nickname: app_commands.Range[str, 1, 25],
    ):
        """
        Change a user display name.

        Args:
            itx: Interaction
            member: User
            nickname: New nickname
        """
        old = self.bot.all_users[member]["nickname"]
        self.bot.all_users[member]["nickname"] = nickname
        await self.bot.database.set(
            "UPDATE users SET nickname=$1 WHERE user_id=$2", nickname, member
        )
        await itx.response.send_message(
            f"Changing {old} ({member}) nickname to {nickname}"
        )

    @mod.command(name="link-member")
    @app_commands.autocomplete(fake_user=cogs.users_autocomplete)
    async def link_member(
        self, itx: core.Interaction[core.Genji], fake_user: str, member: discord.Member
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
            raise utils.InvalidFakeUser
        if fake_user >= 100000:
            raise utils.InvalidFakeUser
        fake_name = await itx.client.database.get_row(
            "SELECT * FROM users WHERE user_id=$1", fake_user
        )
        if not fake_name:
            raise utils.InvalidFakeUser

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
    async def link_fake_to_member(
        itx: core.Interaction[core.Genji], fake_id: int, member: discord.Member
    ):
        await itx.client.database.set(
            "UPDATE map_creators SET user_id=$2 WHERE user_id=$1", fake_id, member.id
        )
        await itx.client.database.set(
            "UPDATE map_ratings SET user_id=$2 WHERE user_id=$1", fake_id, member.id
        )
        await itx.client.database.set(
            "DELETE FROM users WHERE user_id=$1",
            fake_id,
        )

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
        itx: core.Interaction[core.Genji],
        action: app_commands.Choice[str],
        map_code: app_commands.Transform[str, utils.MapCodeTransformer],
    ):
        await itx.response.defer(ephemeral=True)
        if action.value == "archive" and itx.client.map_cache[map_code]["archived"] is False:
            value = True

        elif action.value == "unarchive" and itx.client.map_cache[map_code]["archived"] is True:
            value = False
        else:
            await itx.edit_original_response(
                content=f"**{map_code}** has already been {action.value}d."
            )
            return
        itx.client.map_cache[map_code]["archived"] = value
        await itx.client.database.set(
            """UPDATE maps SET archived = $1 WHERE map_code = $2""",
            value,
            map_code,
        )
        await itx.edit_original_response(content=f"**{map_code}** has been {action.value}d.")
        itx.client.dispatch("newsfeed_archive", itx, map_code, action.value)

    @map.command()
    @app_commands.choices(value=utils.DIFFICULTIES_CHOICES)
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    async def difficulty(
        self,
        itx: core.Interaction[core.Genji],
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
        await utils.update_affected_users(itx, map_code)

    @map.command()
    @app_commands.autocomplete(map_code=cogs.map_codes_autocomplete)
    @app_commands.choices(value=utils.ALL_STARS_CHOICES)
    async def rating(
        self,
        itx: core.Interaction[core.Genji],
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

    # TODO: Delete map ?


async def setup(bot: core.Genji):
    await bot.add_cog(ModCommands(bot))
