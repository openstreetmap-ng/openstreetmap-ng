import logging
import pathlib
from functools import cached_property
from typing import NamedTuple

import yaml

from config import DEFAULT_LANGUAGE
from limits import LANGUAGE_CODE_MAX_LENGTH


class LanguageInfo(NamedTuple):
    code: str
    english_name: str
    native_name: str

    @cached_property
    def display_name(self) -> str:
        return f'{self.english_name} ({self.native_name})'


def _load_languages() -> dict[str, LanguageInfo]:
    # TODO: test "no" code
    with pathlib.Path('config/languages.yml').open() as f:
        data: dict = yaml.safe_load(f)

    return {
        code: LanguageInfo(
            code=code,
            english_name=v['english'],
            native_name=v['native'],
        )
        for code, v in data.items()
    }


_languages = _load_languages()
_languages_lower_map = {k.casefold(): k for k in _languages}

logging.info('Loaded %d languages', len(_languages))

if DEFAULT_LANGUAGE not in _languages:
    raise RuntimeError(f'{DEFAULT_LANGUAGE=!r} not found in languages')

for code in _languages:
    if len(code) > LANGUAGE_CODE_MAX_LENGTH:
        raise RuntimeError(f'Language code {code=!r} is too long ({len(code)=} > {LANGUAGE_CODE_MAX_LENGTH=})')


def normalize_language_case(code: str) -> str:
    """
    Normalize language code case.

    >>> fix_language_case('EN')
    'en'
    >>> fix_language_case('NonExistent')
    'NonExistent'
    """

    if code in _languages:
        return code
    return _languages_lower_map.get(code.casefold(), code)


def get_language_info(normalized_code: str) -> LanguageInfo | None:
    """
    Get `LanguageInfo` by normalized code.
    """

    return _languages.get(normalized_code, None)
