import typing


class Formatter:

    def __init__(self, data: dict[str, typing.Any | None]):
        self.values = data

    @staticmethod
    def wrap_str_code_block(value: str) -> str:
        return f"`{value}`"

    @staticmethod
    def formatting_character(value: bool) -> str:
        if value:
            return "┣"
        return "┗"

    def format_map(self) -> str:
        res = ""
        length = len(self.values)
        for i, (name, value) in enumerate(self.values.items()):
            char = self.formatting_character(i + 1 < length)
            wrapped_name = self.wrap_str_code_block(name)
            res += f"{char} {wrapped_name} {value}\n"

        return res
