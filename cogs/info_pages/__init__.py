from cogs.info_pages.info_page import InfoPage


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(InfoPage(bot))
