from typing import NamedTuple, NewType

LocaleCode = NewType('LocaleCode', str)


class LocaleName(NamedTuple):
    code: LocaleCode
    english: str
    native: str
    installed: bool

    @property
    def display_name(self) -> str:
        return self.english if (self.english == self.native) else f'{self.english} ({self.native})'
