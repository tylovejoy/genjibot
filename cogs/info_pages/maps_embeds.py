import discord

MAP_SUBMISSIONS_INFO = discord.Embed(
    title="How to submit?",
    description=(
        "The process is simple. Start by typing the following command in any channel that you can type in:\n"
        "`/submit-map`\n"
        "Three required arguments will be necessary enter the command with an additional five optional arguments. "
        "Discord will highlight the inputs in red if it's invalid or missing.\n\n"
        "__REQUIRED ARGUMENTS:__\n"
        "- `map_code`: Overwatch Workshop code\n"
        "- `map_name`: Overwatch Map\n"
        "- `checkpoint_count`: Number of checkpoints your map has\n\n"
        "__OPTIONAL ARGUMENTS:__\n"
        "- `description`: Extra information or details you want to add to the map\n"
        "- `guide_url`: a valid URL to a guide for the map\n"
        "- `gold`: Time to beat for a *Gold* medal\n"
        "- `silver`: Time to beat for a *Silver* medal\n"
        "- `bronze`: Time to beat for a *Bronze* medal\n\n"
        "Once you enter the command, dropdown boxes will appear.\n"
        "You must select a map type and a difficulty. If there are mechanics or restrictions, "
        "you can select multiple of those.\n\n"
        "When you finish selecting those options, you can continue with the *green* button. "
        "Or you can cancel the process with the red button.\n"
        "A final overview will appear where you can double check the data you have entered. If it is all correct, "
        "then press the *green* button. If not, click the red button to cancel the process.\n"
        "Once submitted, the map must go through a playtesting phase.\n"
    ),
    color=discord.Color.red(),
)
MAP_SUBMISSIONS_INFO.set_image(url="https://bkan0n.com/assets/images/map_submission_1.png")

MAP_PLAYTESTING_INFO = discord.Embed(
    title="Playtesting Info",
    description=(
        ":bangbang: You _must_ have submitted a completion for the map to vote :bangbang:\n\n"
        "- Each difficulty requires a specific amount of *votes* **and** *completion submissions*.\n"
        "- Creators cannot vote for their map as their map submission contains their best estimate of difficulty.\n"
        "- Playtesters will give the creator tips on how to make the map better, or what specifically needs to change, "
        "if there are any glaring issues, etc."
    ),
    color=discord.Color.red(),
)
MAP_PLAYTESTING_INFO.set_image(url="https://bkan0n.com/assets/images/map_submit_flow.png")

DIFF_TECH_CHART = discord.Embed(
    title="Difficulty / Tech Chart",
)
DIFF_TECH_CHART.set_image(url="https://bkan0n.com/assets/images/diff_techs.png")
