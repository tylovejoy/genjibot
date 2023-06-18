import discord
from discord.ext import commands

TICKET_CHANNEL = 1120029553998450719
MODMAIL_ROLE = 1120076555293569081


def ticket_thread_check():
    def predicate(ctx: commands.Context):
        return (
            isinstance(ctx.channel, discord.Thread)
            and ctx.channel.parent_id == TICKET_CHANNEL
        )

    return commands.check(predicate)
