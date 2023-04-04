import typing


class Formatter:
    def __init__(self, data: dict[str, typing.Any | None]):
        self.values = data

    @staticmethod
    def wrap_str_code_block(value: str) -> str:
        return f"`{value}`"

    @staticmethod
    def formatting_character(value: bool) -> str:
        return "┣" if value else "┗"

    def format_map(self) -> str:
        res = ""
        filtered_values = {
            k: v
            for k, v in self.values.items()
            if v is not False and v is not None and v != ""
        }.items()
        length = len(filtered_values)
        for i, (name, value) in enumerate(filtered_values):
            char = self.formatting_character(i + 1 < length)
            wrapped_name = self.wrap_str_code_block(name)
            res += f"{char} {wrapped_name} {value}\n"
        return res
