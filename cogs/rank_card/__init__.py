from cogs.rank_card.rank_card import RankCard


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(RankCard(bot))
