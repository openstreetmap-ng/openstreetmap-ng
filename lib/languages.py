import logging
from functools import cached_property
from typing import NamedTuple

import yaml

from config import DEFAULT_LANGUAGE


class Language(NamedTuple):
    code: str
    english_name: str
    native_name: str

    @cached_property
    def display_name(self) -> str:
        return f'{self.english_name} ({self.native_name})'


# TODO: test "no" code
with open('config/languages.yml') as f:
    _languages_: dict = yaml.safe_load(f)

_languages: dict[str, Language] = {
    code: Language(
        code=code,
        english_name=v['english'],
        native_name=v['native']
    ) for code, v in _languages_.items()
}

_languages_lower_map = {k.lower(): k for k in _languages}

logging.info('Loaded %d languages', len(_languages))

if DEFAULT_LANGUAGE not in _languages:
    raise RuntimeError(f'{DEFAULT_LANGUAGE=!r} not found in languages')

del _languages_  # cleanup


def fix_language_case(code: str) -> str:
    if code in _languages:
        return code

    return _languages_lower_map.get(code.lower(), code)


def get_language(code: str) -> Language | None:
    return _languages.get(code, None)
