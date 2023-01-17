import math

import discord

# TODO: Hardcoded LIVE
GUILD_ID = 968951072599187476  # 195387617972322306

# TODO: Hardcoded LIVE
STAFF = 1021889200242573322  # 1047262740315643925
PLAYTESTER = 1054779896305569792
TAG_MAKER = 1002267404816093244

#
CONFIRM = "<:_:1052666519487795261>"
# HALF_VERIFIED = "<:_:1042541868723998871>"


UNVERIFIED = "<:_:1042541865821556746>"

FULLY_VERIFIED = "<a:_:1053038647978512535>"
FULLY_VERIFIED_GOLD = "<a:_:1053038660553027707>"
FULLY_VERIFIED_SILVER = "<a:_:1053038666114666669>"
FULLY_VERIFIED_BRONZE = "<a:_:1053038654274162718>"

PARTIAL_VERIFIED = "<:_:1053038667935002727>"
# PARTIAL_VERIFIED_GOLD = "<:_:1053038670527074434>"
# PARTIAL_VERIFIED_SILVER = "<:_:1053038671688900629>"
# PARTIAL_VERIFIED_BRONZE = "<:_:1053038669168136302>"

TIME = "⌛"

CONFIRM_EMOJI = discord.PartialEmoji.from_str(CONFIRM)
# HALF_VERIFIED_EMOJI = discord.PartialEmoji.from_str(HALF_VERIFIED)
UNVERIFIED_EMOJI = discord.PartialEmoji.from_str(UNVERIFIED)

_FIRST = "<:_:1043226244575142018>"
_SECOND = "<:_:1043226243463659540>"
_THIRD = "<:_:1043226242335391794>"

PLACEMENTS = {
    1: _FIRST,
    2: _SECOND,
    3: _THIRD,
}


STAR = "★"
EMPTY_STAR = "☆"


def create_stars(rating: int | float | None) -> str:
    if not rating:
        return "Unrated"
    filled = math.ceil(rating) * STAR
    return filled + ((6 - len(filled)) * EMPTY_STAR)


def _generate_all_stars() -> list[str]:
    return [create_stars(x) for x in range(1, 7)]


ALL_STARS = _generate_all_stars()
ALL_STARS_CHOICES = [
    discord.app_commands.Choice(name=x, value=i)
    for i, x in enumerate(ALL_STARS, start=1)
]

# TODO: Hardcoded LIVE
NEW_MAPS = 1060045563883700255  # 856602254769782835
PLAYTEST = 988812516551438426
VERIFICATION_QUEUE = 992134125253316699  # 811467249100652586
NEWSFEED = 1055501059352698930
RECORDS = 979491570237730817  # 801496775390527548


# TODO: Hardcoded LIVE
class Roles:
    NINJA = 989188787106119690
    # NINJA_PLUS = 1034572581061263400
    JUMPER = 989184572224843877
    JUMPER_PLUS = 1034572630184968313
    SKILLED = 989184754840657920
    SKILLED_PLUS = 1034572662271389726
    PRO = 989184805843378226
    PRO_PLUS = 1034572705393016954
    MASTER = 989184828832370688
    MASTER_PLUS = 1034572740994269335
    GRANDMASTER = 989188737718169642
    GRANDMASTER_PLUS = 1034572780148117524
    GOD = 989184852639223838
    GOD_PLUS = 1034572827807985674

    MAP_MAKER = 1001927190935515188

    @classmethod
    def roles_per_rank(cls, rank_num: int) -> list[int]:
        return cls.ranks[0 : rank_num + 1]

    @classmethod
    def ranks(cls) -> list[int]:
        return [
            cls.NINJA,
            cls.JUMPER,
            cls.SKILLED,
            cls.PRO,
            cls.MASTER,
            cls.GRANDMASTER,
            cls.GOD,
        ]

    @classmethod
    def ranks_plus(cls) -> list[int]:
        return [
            0,
            cls.JUMPER_PLUS,
            cls.SKILLED_PLUS,
            cls.PRO_PLUS,
            cls.MASTER_PLUS,
            cls.GRANDMASTER_PLUS,
            cls.GOD_PLUS,
        ]

    @classmethod
    async def find_highest_rank(cls, user: discord.Member) -> int:
        """Find the highest rank a user has.

        Args:
            user (discord.Member): User to check

        Returns:
            int: index for highest rank
        """
        ids = [r.id for r in user.roles]
        res = 0
        for i, role in enumerate(cls.ranks()):
            if role in ids:
                res += 1
        return res
