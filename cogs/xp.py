from discord.ext import commands


class XPCog(commands.Cog): ...


async def setup(bot):
    await bot.add_cog(XPCog(bot))
