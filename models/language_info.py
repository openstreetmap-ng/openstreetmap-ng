from typing import NamedTuple


class LanguageInfo(NamedTuple):
    code: str
    english_name: str
    native_name: str

    @property
    def display_name(self) -> str:
        return f'{self.english_name} ({self.native_name})'
