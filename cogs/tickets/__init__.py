from cogs.tickets.tickets import TicketSystem


async def setup(bot):
    """Add Cog to Discord bot."""
    await bot.add_cog(TicketSystem(bot))
