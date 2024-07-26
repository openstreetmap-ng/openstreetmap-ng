from typing import NamedTuple


class LocaleName(NamedTuple):
    code: str
    english: str
    native: str
    installed: bool

    @property
    def display_name(self) -> str:
        return self.english if (self.english == self.native) else f'{self.english} ({self.native})'
