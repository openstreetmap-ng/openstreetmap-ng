import gzip
import json
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from typing import NamedTuple
from urllib.parse import unquote_plus

import anyio
from anyio import CapacityLimiter, create_task_group

from app.config import CONFIG_DIR
from app.lib.retry import retry
from app.utils import HTTP

_download_limiter = CapacityLimiter(6)  # max concurrent downloads
_wiki_pages_path = CONFIG_DIR / 'wiki_pages.json'


class WikiPageInfo(NamedTuple):
    key: str
    value: str
    locale: str


async def get_sitemap_links() -> Sequence[str]:
    r = await HTTP.get('https://wiki.openstreetmap.org/sitemap-index-wiki.xml')
    r.raise_for_status()
    matches = re.finditer(r'https://wiki\.openstreetmap\.org/sitemap-wiki-NS_\d+-\d+.xml.gz', r.text)
    result = tuple(match[0] for match in matches)
    print(f'[🔍] Discovered {len(result)} sitemaps')
    return result


@retry(timedelta(minutes=1))
async def download_and_analyze(sitemap_url: str) -> Sequence[WikiPageInfo]:
    async with _download_limiter:
        r = await HTTP.get(sitemap_url)
        r.raise_for_status()

    text = gzip.decompress(r.content).decode()
    result: list[WikiPageInfo] = []

    for match in re.finditer(r'/(?:(?P<locale>[\w-]+):)?(?P<page>(?:Key|Tag):.*?)</loc>', text):
        locale: str = match['locale'] or ''
        locale = unquote_plus(locale)

        # skip talk pages
        if locale.startswith(('Talk', 'Proposal')) or locale.endswith(('_talk', '_proposal')):
            continue

        page: str = match['page']
        page = unquote_plus(page)

        if page.startswith('Key:'):
            # skip key pages with values
            if '=' in page:
                continue
            key, value = page[4:], '*'
        else:
            # skip tag pages without values
            if '=' not in page:
                continue
            key, value = page[4:].split('=', 1)

        result.append(WikiPageInfo(key, value, locale))

    print(f'[✅] {sitemap_url!r}: {len(result)} pages')
    return result


async def main():
    urls = await get_sitemap_links()
    infos: list[WikiPageInfo] = []

    async def sitemap_task(sitemap_url: str):
        infos.extend(await download_and_analyze(sitemap_url))

    async with create_task_group() as tg:
        for url in urls:
            tg.start_soon(sitemap_task, url)

    key_values_locales: dict[str, dict[str | None, set[str]]] = defaultdict(lambda: defaultdict(set))
    for info in infos:
        key_values_locales[info.key][info.value].add(info.locale)

    result = {
        key: {
            value: sorted(locales)  #
            for value, locales in values.items()
        }
        for key, values in key_values_locales.items()
    }

    buffer = json.dumps(result, indent=2, sort_keys=True) + '\n'
    await _wiki_pages_path.write_text(buffer)


if __name__ == '__main__':
    anyio.run(main)
