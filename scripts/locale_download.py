import asyncio
import re
from asyncio import Semaphore, TaskGroup
from datetime import timedelta
from pathlib import Path

import orjson

from app.lib.locale import LocaleName
from app.lib.retry import retry
from app.models.types import LocaleCode
from app.utils import HTTP

_download_dir = Path('config/locale/download')
_download_limiter = Semaphore(8)  # max concurrent downloads
_extra_names_path = Path('config/locale/extra_names.json')
_names_path = Path('config/locale/names.json')


async def get_download_locales() -> tuple[LocaleCode, ...]:
    r = await HTTP.get('https://translatewiki.net/wiki/Special:ExportTranslations', params={'group': 'out-osm-site'})
    r.raise_for_status()
    matches = re.finditer(r"<option value='([\w-]+)'.*?>\1 - ", r.text)
    return tuple(LocaleCode(match[1]) for match in matches)


@retry(timedelta(minutes=2))
async def download_locale(locale: LocaleCode) -> LocaleName | None:
    async with _download_limiter:
        r = await HTTP.get(
            'https://translatewiki.net/wiki/Special:ExportTranslations',
            params={'group': 'out-osm-site', 'language': locale, 'format': 'export-to-file'},
        )
        r.raise_for_status()

        content_disposition = r.headers.get('Content-Disposition')
        if content_disposition is None:
            return None  # missing translation

        match_locale = re.search(r'filename="([\w-]+)\.yml"', content_disposition)
        if match_locale is None:
            raise ValueError(f'Failed to match filename for {locale!r}')

        locale = LocaleCode(match_locale[1])
        if locale == 'x-invalidLanguageCode':
            print(f'[❔] {locale}: invalid language code')
            return None

    match = re.match(r'# Messages for (.+?) \((.+?)\)', r.text)
    if match is None:
        raise ValueError(f'Failed to match language names for {locale!r}')

    english_name = match[1].strip()
    native_name = match[2].strip()
    if english_name == 'Message documentation':
        print(f'[❔] {locale}: not a language')
        return None

    target_path = _download_dir.joinpath(f'{locale}.yaml')
    if not target_path.is_file() or (target_path.read_bytes()) != r.content:
        target_path.write_bytes(r.content)
        print(f'[✅] Updated: {locale}')
    else:
        print(f'[✅] Already up-to-date: {locale}')

    return LocaleName(
        code=locale,
        english=english_name,
        native=native_name,
        installed=True,
    )


def add_extra_locales_names(locales_names: list[LocaleName]):
    extra_locales_names: dict[LocaleCode, dict] = orjson.loads(_extra_names_path.read_bytes())

    for ln in locales_names:
        extra_locales_names.pop(ln.code, None)

    for code, data in extra_locales_names.items():
        english_name: str = data['english']
        native_name: str = data['native']
        locales_names.append(
            LocaleName(
                code=code,
                english=english_name,
                native=native_name,
                installed=True,
            )
        )
        print(f'[➕] Added extra name: {code}')  # noqa: RUF001


async def main():
    _download_dir.mkdir(parents=True, exist_ok=True)

    locales = await get_download_locales()

    async with TaskGroup() as tg:
        tasks = tuple(tg.create_task(download_locale(locale)) for locale in locales)

    locales_names: list[LocaleName] = list(filter(None, (task.result() for task in tasks)))
    add_extra_locales_names(locales_names)

    locales_names.sort(key=lambda v: v.code)
    locales_names_dict = tuple(ln._asdict() for ln in locales_names)
    buffer = orjson.dumps(
        locales_names_dict, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE
    )
    _names_path.write_bytes(buffer)


if __name__ == '__main__':
    asyncio.run(main())
