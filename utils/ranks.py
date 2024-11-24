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

DIFFICULTIES = list(filter(lambda y: not ("-" in y or "+" in y), DIFFICULTIES_EXT))


def generate_difficulty_ranges(
    top_level: bool = False,
) -> dict[str, tuple[float, float]]:
    """Generate ranges between difficulties."""
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
TOP_DIFFICULTY_RANGES_MIDPOINT = {k: round((v[0] + v[1]) / 2, 2) for k, v in TOP_DIFFICULTIES_RANGES.items()}

ALL_DIFFICULTY_RANGES_MIDPOINT = {k: round((v[0] + v[1]) / 2, 2) for k, v in DIFFICULTIES_RANGES.items()}

DIFFICULTIES_CHOICES = [app_commands.Choice(name=x, value=x) for x in DIFFICULTIES_EXT]


def convert_num_to_difficulty(value: float) -> str:
    """Convert value to difficulty."""
    res = "Hell"
    for diff, _range in DIFFICULTIES_RANGES.items():
        if float(_range[0]) <= float(value) + 0.01 < float(_range[1]):
            res = diff
            break
    return res
