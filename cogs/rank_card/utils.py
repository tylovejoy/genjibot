import imagetext_py as ipy
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

_COMPLETION_BAR_TOTAL_LENGTH = 325
_COMPLETION_BAR_X_POSITION = 109
_COMPLETION_BAR_HEIGHT = 32

_MEDAL_BOX_WIDTH = 33

_LABEL_X_POSITION = 437
_LABEL_WIDTH = 65

_MISC_DATA_Y_POSITION = 306
_MISC_DATA_HEIGHT = 81
_MISC_DATA_WIDTH = 91

_MAP_COUNT_X_POSITION = 672
_PLAYTEST_COUNT_X_POSITION = 771
_WORLD_RECORDS_COUNT_X_POSITION = 869

_NAME_X_POSITION = _MAP_COUNT_X_POSITION
_NAME_Y_POSITION = 403
_NAME_WIDTH = 289
_NAME_HEIGHT = 41


_COMPLETION_BAR_Y_POSITIONS = {
    "Beginner": 61,
    "Easy": 119,
    "Medium": 176,
    "Hard": 234,
    "Very Hard": 292,
    "Extreme": 349,
    "Hell": 407,
}

_COMPLETION_BAR_COLORS = {
    "Beginner": "#00ff1a",
    "Easy": "#cdff3a",
    "Medium": "#fbdf00",
    "Hard": "#ff9700",
    "Very Hard": "#ff4500",
    "Extreme": "#ff0000",
    "Hell": "#9a0000",
}

_MEDAL_X_POSITIONS = {
    "gold": 518,
    "silver": 564,
    "bronze": 611,
}

RANKS = (
    "Ninja",
    "Jumper",
    "Skilled",
    "Pro",
    "Master",
    "Grandmaster",
    "God",
)

ipy.FontDB.LoadFromDir("./assets")
font = ipy.FontDB.Query("notosans china1 china2 japanese korean")


class RankCardBuilder:
    def __init__(self, data):
        self._data = data

        self._rank_card = Image.open(f"assets/layer0/{self._data['bg']}.png").convert(
            "RGBA"
        )
        self._draw = ImageDraw.Draw(self._rank_card)
        self._small_font = ImageFont.truetype("assets/Calibri.ttf", 20)
        self._large_font = ImageFont.truetype("assets/Calibri.ttf", 30)
        self._name_font = ImageFont.truetype("assets/Calibri.ttf", 30)

    def create_card(self):
        self._add_layer1()
        for category in _COMPLETION_BAR_COLORS:
            self._create_completion_bar(
                category,
                self._data[category]["completed"] / self._data[category]["total"],
            )
        self._add_layer2()
        for category in _COMPLETION_BAR_COLORS:
            self._add_completion_labels(
                category,
                self._data[category]["completed"],
                self._data[category]["total"],
            )
        self._add_rank_emblem()
        self._draw_maps_count()
        self._draw_playtests_count()
        self._draw_world_records_count()
        self._draw_name()
        return self._rank_card

    def _add_layer1(self):
        self._paste_transparent_image("assets/layer1.png")

    def _add_layer2(self):
        self._paste_transparent_image("assets/layer2.png")

    def _add_completion_labels(self, category: str, completed: int, total: int):
        y_position = _COMPLETION_BAR_Y_POSITIONS[category]
        text = f"{completed}/{total}"
        position = self._get_center_x_position(
            _LABEL_WIDTH, _LABEL_X_POSITION, text, self._small_font
        )
        self._draw.text(
            (position, y_position + _COMPLETION_BAR_HEIGHT // 4),
            text,
            font=self._small_font,
            fill=(255, 255, 255),
        )

    def _create_completion_bar(self, category: str, ratio: float):
        y_position = _COMPLETION_BAR_Y_POSITIONS[category]
        bar_length = _COMPLETION_BAR_TOTAL_LENGTH * ratio

        for medal in ["gold", "silver", "bronze"]:
            self._add_completion_medals(category, medal)

        if ratio == 0:
            return

        self._draw.rectangle(
            (
                (_COMPLETION_BAR_X_POSITION, y_position),
                (
                    _COMPLETION_BAR_X_POSITION + bar_length,
                    y_position + _COMPLETION_BAR_HEIGHT,
                ),
            ),
            fill=_COMPLETION_BAR_COLORS[category],
        )

    def _add_completion_medals(self, category: str, medal: str):
        y_position = _COMPLETION_BAR_Y_POSITIONS[category]
        text = f"{self._data[category][medal]}"
        position = self._get_center_x_position(
            _MEDAL_BOX_WIDTH, _MEDAL_X_POSITIONS[medal], text, self._small_font
        )

        self._draw.text(
            (position, y_position + _COMPLETION_BAR_HEIGHT // 4),
            text,
            font=self._small_font,
            fill=(255, 255, 255),
        )

    def _add_rank_emblem(self):
        self._paste_transparent_image(f"assets/layer3/{self._data['rank'].lower()}.png")

    def _paste_transparent_image(self, path: str):
        layer = Image.open(path).convert("RGBA")
        self._rank_card.paste(layer, None, layer)

    def _draw_maps_count(self):
        text = f"{self._data['maps']}"
        position = self._get_center_x_position(
            _MISC_DATA_WIDTH, _MAP_COUNT_X_POSITION, text, self._large_font
        )
        self._draw.text(
            (position, _MISC_DATA_Y_POSITION + (_MISC_DATA_HEIGHT // 4)),
            text,
            font=self._large_font,
            fill=(255, 255, 255),
        )

    def _draw_playtests_count(self):
        text = f"{self._data['playtests']}"
        position = self._get_center_x_position(
            _MISC_DATA_WIDTH, _PLAYTEST_COUNT_X_POSITION, text, self._large_font
        )
        self._draw.text(
            (position, _MISC_DATA_Y_POSITION + (_MISC_DATA_HEIGHT // 4)),
            text,
            font=self._large_font,
            fill=(255, 255, 255),
        )

    def _draw_world_records_count(self):
        text = f"{self._data['world_records']}"
        position = self._get_center_x_position(
            _MISC_DATA_WIDTH, _WORLD_RECORDS_COUNT_X_POSITION, text, self._large_font
        )
        self._draw.text(
            (position, _MISC_DATA_Y_POSITION + (_MISC_DATA_HEIGHT // 4)),
            text,
            font=self._large_font,
            fill=(255, 255, 255),
        )

    def _draw_name(self):
        with ipy.Writer(self._rank_card) as w:
            text = f"{self._data['name']}"
            position = self._get_center_x_position(
                _NAME_WIDTH, _NAME_X_POSITION, text, self._large_font
            )
            w.draw_text_wrapped(
                text=text,
                x=position,
                y=_NAME_Y_POSITION + (_NAME_HEIGHT // 4) - 8,
                ax=0,
                ay=0,
                width=500,
                size=30,
                font=font,
                fill=ipy.Paint.Color((255, 255, 255, 255)),
                stroke_color=ipy.Paint.Rainbow((0.0, 0.0), (256.0, 256.0)),
                draw_emojis=True,
            )

    def _get_center_x_position(
        self, width: int, initial_pos: int, text: str, font: FreeTypeFont
    ):
        return (width // 2 - self._draw.textlength(text, font) // 2) + initial_pos
