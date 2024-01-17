import logging
import pathlib

import cython
import yaml

from src.config import CONFIG_DIR, DEFAULT_LANGUAGE
from src.limits import LANGUAGE_CODE_MAX_LENGTH
from src.models.language_info import LanguageInfo

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')


# TODO: test "no" code
with pathlib.Path(CONFIG_DIR / 'languages.yml').open() as f:
    data: dict = yaml.safe_load(f)

_languages: dict[str, LanguageInfo] = {
    code: LanguageInfo(
        code=code,
        english_name=v['english'],
        native_name=v['native'],
    )
    for code, v in data.items()
}

_languages_lower_map = {k.casefold(): k for k in _languages}

logging.info('Loaded %d languages', len(_languages))

# check that default language exists
if DEFAULT_LANGUAGE not in _languages:
    raise RuntimeError(f'{DEFAULT_LANGUAGE=!r} not found in languages')

# check that all language codes are short enough
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
