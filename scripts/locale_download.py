import re
from collections.abc import Sequence
from datetime import timedelta

import anyio
import orjson
from anyio import CapacityLimiter

from app.config import LOCALE_DIR
from app.lib.retry import retry
from app.models.locale_name import LocaleName
from app.utils import HTTP

_download_dir = LOCALE_DIR / 'download'
_download_limiter = CapacityLimiter(8)  # max concurrent downloads
_extra_names_path = LOCALE_DIR / 'extra_names.json'
_names_path = LOCALE_DIR / 'names.json'


async def get_download_locales() -> Sequence[str]:
    r = await HTTP.get('https://translatewiki.net/wiki/Special:ExportTranslations?group=out-osm-site')
    r.raise_for_status()
    matches = re.finditer(r"<option value='([\w-]+)'.*?>\1 - ", r.text)
    return tuple(match[1] for match in matches)


@retry(timedelta(minutes=2))
async def download_locale(locale: str) -> LocaleName | None:
    async with _download_limiter:
        r = await HTTP.get(
            f'https://translatewiki.net/wiki/Special:ExportTranslations?group=out-osm-site&language={locale}&format=export-to-file'
        )
        r.raise_for_status()

    content_disposition = r.headers.get('Content-Disposition')
    if content_disposition is None:
        # missing translation
        return None

    locale = re.search(r'filename="([\w-]+)\.yml"', content_disposition)[1]

    if locale == 'x-invalidLanguageCode':
        print(f'[❔] {locale}: invalid language code')
        return None

    match = re.match(r'# Messages for (.+?) \((.+?)\)', r.text)
    english_name = match[1].strip()
    native_name = match[2].strip()

    if english_name == 'Message documentation':
        print(f'[❔] {locale}: not a language')
        return None

    target_path = _download_dir / f'{locale}.yaml'

    if not await target_path.is_file() or (await target_path.read_bytes()) != r.content:
        await target_path.write_bytes(r.content)
        print(f'[✅] Updated: {locale}')
    else:
        print(f'[✅] Already up-to-date: {locale}')

    return LocaleName(
        code=locale,
        english=english_name,
        native=native_name,
    )


async def add_extra_locales_names(locales_names: list[LocaleName]):
    buffer = await _extra_names_path.read_bytes()
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
        print(f'[➕] Added extra name: {code}')  # noqa: RUF001


async def main():
    await _download_dir.mkdir(parents=True, exist_ok=True)

    locales = await get_download_locales()
    locales_names: list[LocaleName] = []

    async def process_locale(locale: str):
        if (locale_name := await download_locale(locale)) is not None:
            locales_names.append(locale_name)

    async with anyio.create_task_group() as tg:
        for locale in locales:
            tg.start_soon(process_locale, locale)

    await add_extra_locales_names(locales_names)

    locales_names.sort(key=lambda v: v.code)

    buffer = orjson.dumps(
        tuple(ln._asdict() for ln in locales_names),
        option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
    )
    await _names_path.write_bytes(buffer)


if __name__ == '__main__':
    anyio.run(main, backend_options={'use_uvloop': True})
