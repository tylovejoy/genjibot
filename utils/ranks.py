from discord import app_commands

DIFFICULTIES_EXT = [
    "Beginner",
    "Easy -",
    "Easy",
    "Easy +",
    "Medium -",
    "Medium",
    "Medium +",
    "Hard -",
    "Hard",
    "Hard +",
    "Very Hard -",
    "Very Hard",
    "Very Hard +",
    "Extreme -",
    "Extreme",
    "Extreme +",
    "Hell",
]

DIFFICULTIES = [
    x for x in filter(lambda y: not ("-" in y or "+" in y), DIFFICULTIES_EXT)
]


def generate_difficulty_ranges(top_level=False) -> dict[str, tuple[float, float]]:
    ranges = {}
    range_length = 10 / len(DIFFICULTIES_EXT)
    cur_range = 0
    for d in DIFFICULTIES_EXT:
        ranges[d] = (round(cur_range, 2), round(cur_range + range_length, 2))
        cur_range += range_length

    if top_level:
        temp_ranges = {}

        for k, v in ranges.items():
            key = k.rstrip(" -").rstrip(" +")
            if key in temp_ranges:
                temp_ranges[key] = (
                    min(temp_ranges[key][0], v[0]),
                    max(temp_ranges[key][1], v[1]),
                )
            else:
                temp_ranges[key] = v

        ranges = temp_ranges

    return ranges


DIFFICULTIES_RANGES = generate_difficulty_ranges()
TOP_DIFFICULTIES_RANGES = generate_difficulty_ranges(True)
TOP_DIFFICULTY_RANGES_MIDPOINT = {
    k: (v[0] + v[1]) / 2 for k, v in TOP_DIFFICULTIES_RANGES.items()
}

DIFFICULTIES_CHOICES = [app_commands.Choice(name=x, value=x) for x in DIFFICULTIES_EXT]


def allowed_difficulties(rank_number: int) -> list[str | None]:
    ranks = []
    if rank_number >= 4:
        ranks += DIFFICULTIES_EXT[0:10]
    if rank_number >= 5:
        ranks += DIFFICULTIES_EXT[10:13]
    if rank_number >= 6:
        ranks += DIFFICULTIES_EXT[13:16]
    if rank_number >= 7:
        ranks += DIFFICULTIES_EXT[16:19]
    return ranks


def convert_num_to_difficulty(value: float | int) -> str:
    res = "Hell"
    for diff, _range in DIFFICULTIES_RANGES.items():
        if _range[0] <= value < _range[1]:
            res = diff
            break
    return res
