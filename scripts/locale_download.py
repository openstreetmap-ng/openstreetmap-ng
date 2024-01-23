import re
from collections.abc import Sequence
from datetime import timedelta

import anyio
import orjson
from anyio import CapacityLimiter, Path

from app.config import LOCALE_DIR
from app.lib.retry import retry
from app.models.locale_name import LocaleName
from app.utils import HTTP

_download_dir = LOCALE_DIR / 'download'
_download_limiter = CapacityLimiter(8)  # max concurrent downloads


async def get_download_locales() -> Sequence[str]:
    r = await HTTP.get('https://translatewiki.net/wiki/Special:ExportTranslations?group=out-osm-site')
    r.raise_for_status()
    matches = re.finditer(r"<option value='([\w-]+)'>\1 - ", r.text)
    return [match[1] for match in matches]


@retry(timedelta(minutes=1))
async def download_locale(locale: str) -> LocaleName | None:
    async with _download_limiter:
        r = await HTTP.get(
            f'https://translatewiki.net/wiki/Special:ExportTranslations?group=out-osm-site&language={locale}&format=export-to-file'
        )
        r.raise_for_status()

    content_disposition = r.headers.get('Content-Disposition')
    if content_disposition is None:
        print(f'[❔] {locale!r}: missing translation')
        return None

    locale = re.search(r'filename="([\w-]+)\.yml"', content_disposition)[1]

    if locale == 'x-invalidLanguageCode':
        print(f'[❔] {locale!r}: invalid language code')
        return None

    match = re.match(r'# Messages for (.+?) \((.+?)\)', r.text)
    english_name = match[1].strip()
    native_name = match[2].strip()

    if english_name == 'Message documentation':
        print(f'[❔] {locale!r}: not a language')
        return None

    # treat en-GB as universal english
    if locale == 'en-GB':
        locale = 'en'
        english_name = 'English'
        native_name = 'English'
    elif locale == 'en' or locale == 'en-US':
        raise RuntimeError('This script assumes en-GB is the universal english')

    filepath = _download_dir / f'{locale}.yml'
    await filepath.write_bytes(r.content)
    print(f'[✅] {locale!r}: {english_name} ({native_name})')

    return LocaleName(
        code=locale,
        english=english_name,
        native=native_name,
    )


async def add_extra_locales_names(locales_names: list[LocaleName]):
    buffer = await (Path(__file__).parent / 'extra_locales_names.json').read_bytes()
    extra_locales_names: dict[str, dict] = orjson.loads(buffer)

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
            )
        )
        print(f'[➕] {code!r}: {english_name} ({native_name})')  # noqa: RUF001


async def main():
    await _download_dir.mkdir(parents=True, exist_ok=True)

    locales = await get_download_locales()
    locales_names: list[LocaleName] = []

    async def process_locale(locale: str):
        if locale_name := await download_locale(locale):
            locales_names.append(locale_name)

    async with anyio.create_task_group() as tg:
        for locale in locales:
            tg.start_soon(process_locale, locale)

    await add_extra_locales_names(locales_names)

    locales_names.sort(key=lambda v: v.code)

    await (LOCALE_DIR / 'names.json').write_bytes(
        orjson.dumps(
            [ln._asdict() for ln in locales_names],
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        )
    )


if __name__ == '__main__':
    anyio.run(main)
