from __future__ import annotations

import typing

import discord
from discord.ext import commands


if typing.TYPE_CHECKING:
    import core


class Test(commands.Cog):
    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: typing.Literal["~", "*", "^"] | None = None,
    ) -> None:
        """
        ?sync -> global sync
        ?sync ~ -> sync current guild
        ?sync * -> copies all global app commands to current guild and syncs
        ?sync ^ -> clears all commands from the current
                        guild target and syncs (removes guild commands)
        ?sync id_1 id_2 -> syncs guilds with id 1 and 2
        >sync $ -> Clears global commands
        """
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            elif spec == "$":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync()
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands "
                f"{'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.is_owner()
    async def xx(self, ctx: commands.Context[core.Genji]):
        members = [(member.id, member.name[:25]) for member in ctx.guild.members]
        await ctx.bot.database.set_many(
            "INSERT INTO users (user_id, nickname, alertable) VALUES ($1, $2, true)",
            [(_id, nick) for _id, nick in members],
        )
        await ctx.send("done")

    @commands.command()
    @commands.is_owner()
    async def xxx(self, ctx: commands.Context[core.Genji]):
        members = [(member.id, member.name[:25]) for member in ctx.guild.members]
        await ctx.bot.database.set_many(
            "INSERT INTO users (user_id, nickname, alertable) VALUES ($1, $2, true)",
            [(_id, nick) for _id, nick in members],
        )
        await ctx.send("done")

    @commands.command()
    @commands.is_owner()
    async def placeholder(self, ctx: commands.Context[core.Genji]):
        await ctx.send("placeholder")

    @commands.command()
    @commands.is_owner()
    async def log(
        self,
        ctx: commands.Context[core.Genji],
        level: typing.Literal["debug", "info", "DEBUG", "INFO"],
    ):
        ctx.bot.logger.setLevel(level.upper())
        await ctx.message.delete()

    # @app_commands.command(name="test")
    # @app_commands.guilds(discord.Object(id=utils.GUILD_ID))
    # async def testing_slash(self, itx: discord.Interaction[core.Genji]) -> None:
    #     command = itx.client.tree.get_app_command("submit-record", guild=utils.GUILD_ID)
    #
    #     embed = utils.GenjiEmbed(
    #         title="Test Help", description=f"Use this comman {command.mention}"
    #     )
    #
    #     await itx.response.send_message(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def close(
        self,
        ctx: commands.Context[core.Genji],
    ):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.channel.send("Bot will be down for a few minutes!")
        await ctx.message.delete()

    @commands.command()
    @commands.is_owner()
    async def open(
        self,
        ctx: commands.Context[core.Genji],
    ):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.channel.send("Back online!")
        await ctx.message.delete()

    @commands.command()
    @commands.is_owner()
    async def enlarge(
        self, ctx: commands.Context[core.Genji], emoji: discord.PartialEmoji | str
    ):
        if isinstance(emoji, discord.PartialEmoji):
            await ctx.send(emoji.url)
        else:
            await ctx.send()

    @commands.command()
    @commands.cooldown(rate=1, per=100000, type=commands.BucketType.guild)
    async def download_maps(self, ctx: commands.Context[core.Genji]):
        f = await ctx.bot.database.copy_from_query(
            """WITH
                required      AS (
                  SELECT
                    CASE
                      WHEN playtest.value >= 9.41 THEN 1
                      WHEN playtest.value >= 7.65 THEN 2
                      WHEN playtest.value >= 5.88 THEN 3
                                                  ELSE 5
                    END AS required_votes, playtest.value, map_code
                    FROM playtest
                   WHERE is_author = TRUE
                ),
            
                playtest_avgs AS
                  (
                    SELECT p.map_code, count(p.value) - 1 AS count, required_votes
            
                      FROM
                        playtest p
                          RIGHT JOIN required rv ON p.map_code = rv.map_code
                     GROUP BY p.map_code, required_votes
                  ),
            
                all_maps      AS (
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
                ),
            ranges ("range", "name") AS (
                 VALUES  ('[0,0.59)'::numrange, 'Beginner'),
                         ('[0.59,2.35)'::numrange, 'Easy'),
                         ('[2.35,4.12)'::numrange, 'Medium'),
                         ('[4.12,5.88)'::numrange, 'Hard'),
                         ('[5.88,7.65)'::numrange, 'Very Hard'),
                         ('[7.65,9.41)'::numrange, 'Extreme'),
                         ('[9.41,10.0]'::numrange, 'Hell')
            )
            
            SELECT
              am.map_name, map_type, am.map_code, am."desc", not am.official as is_playtest,
              am.archived, guide, mechanics, restrictions, am.checkpoints,
              creators, r.name as difficulty, quality, am.gold, am.silver, 
              am.bronze, r.name
              FROM
                all_maps am
                  LEFT JOIN playtest p ON am.map_code = p.map_code AND p.is_author IS TRUE
                  LEFT JOIN playtest_avgs pa ON pa.map_code = am.map_code
                  INNER JOIN ranges r ON r.range @> am.difficulty
             GROUP BY
               am.map_name, map_type, am.map_code, am."desc", am.official, am.archived, guide, mechanics,
               restrictions, am.checkpoints, creators, difficulty, quality, creator_ids, am.gold, am.silver,
               am.bronze, p.thread_id, pa.count, pa.required_votes, r.name
            
            
             ORDER BY
               difficulty, quality DESC"""
        )

        await ctx.send(file=discord.File(fp=f, filename="test.csv"))


async def setup(bot: core.Genji):
    await bot.add_cog(Test(bot))
