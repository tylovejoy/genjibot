import discord

COMPLETION_SUBMISSIONS_INFO = discord.Embed(
    title="How to submit?",
    description=(
        "To get promoted in **Genji Parkour**, follow these steps:\n\n"
        "1. Complete a Genji Parkour map that is in the current map pool.\n"
        "2. Use the `/submit-completion` command in <#1072898844339224627>.\n"
        " - _Note: Maps that aren't currently accepted won't appear in the map code field._\n"
        "3. Your submission will go through a verification process.\n"
        "4. Once verified, you'll receive a notification.\n"
        "\n\n"
        "- By using the `time` argument, you can track your personal bests and compare them to others using the `/completions` command.\n"
        "- Additionally, you must rate the quality of the map. Use the `quality` argument to rate the map on a scale from 1 to 6:\n"
        " - 6: Excellent\n"
        " - 5: Great\n"
        " - 4: Good\n"
        " - 3: Average\n"
        " - 2: Subpar\n"
        " - 1: Poor\n"
    ),
    color=discord.Color.red(),
)

RANKS_INFO = discord.Embed(
    title="Ranks Info",
    description=(
        "- Ranks ***must*** be acquired in order.\n"
        "- To receive a rank you must be ranked in each preceding difficulty.\n"
        "- Submissions are allowed for higher ranks but you will not get the rank until you pass each ranks promotion threshold.\n\n"
        "- See image below for rank thresholds."
    ),
    color=discord.Color.red(),
)
RANKS_INFO.set_image(
    url="http://207.244.249.145/assets/images/rank_chart_landscape.png"
)

MEDALS_INFO = discord.Embed(
    title="Medals Info",
    description=(
        "- To get a +, ++ or +++ rank, you must obtain the same amount of **Bronze**, **Silver**, or **Gold** medals as the rank normally requires (see image below)."
        "- You _must_ post a completion which includes a `time` and a `video` URL showing your run.\n"
        "- You will get a icon next to your name if you have a plus (+, ++, +++) rank!\n"
        "- Once verified, you'll automatically receive your medal.\n"
        "- If medals are added to a map after you have already submitted, you will still get credit.\n\n"
    ),
    color=discord.Color.red(),
)
MEDALS_INFO.set_image(
    url="http://207.244.249.145/assets/images/rank_chart_landscape.png"
)

COMPLETION_SUBMISSION_RULES = discord.Embed(
    title="Submission Rules",
    description=(
        "**Completion Requirements/Guidelines:**\n"
        "- Map code in the screenshot must match the map code in the bot.\n"
        "- Time must be displayed in either the Top 5 leaderboard, or as the announcement in the middle of the screen. If video submission, it must show both.\n"
        "- You cannot use edit the map in anyway using Custom Games settings, Workshop Settings, or any other Workshop code. This includes but is not limited to changing tech bans, gravity, etc.\n"
        "- You are not allowed to use scripts, macros, or anything similar to complete any portion of a map.\n"
        "- You may not used a banned tech (restricted via map author/listed in @GenjiBot#9209) where the ban is non-functional due to Workshop bugs.\n\n"
        "*Records Only:*\n"
        "- Time must be fully visible from 0.00 to the finish. Do not fade in or out while the timer is running.\n"
        "- Video proof is **required** for *World Records* and *Medals*.\n"
        "- Cuts in the video are **not** allowed (between 0.00 and finish).\n"
        "- Game sound is **not** required.\n"
        "- Editing before and after is allowed but it ***cannot*** interfere with timer or any ability to *validate* the submission.\n\n"
        "**Senseis reserve the right to deny any submission for any reason, regardless if it is listed here or not.**"
    ),
    color=discord.Color.red(),
)
