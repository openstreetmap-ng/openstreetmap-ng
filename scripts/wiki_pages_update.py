import gzip
import json
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from urllib.parse import unquote_plus

import anyio
from anyio import CapacityLimiter, create_task_group

from app.config import CONFIG_DIR
from app.lib.retry import retry
from app.utils import HTTP

_download_limiter = CapacityLimiter(8)  # max concurrent downloads
_wiki_pages_path = CONFIG_DIR / 'wiki_pages.json'


async def get_sitemap_links() -> Sequence[str]:
    r = await HTTP.get('https://wiki.openstreetmap.org/sitemap-index-wiki.xml')
    r.raise_for_status()
    matches = re.finditer(r'https://wiki.openstreetmap.org/sitemap-wiki-NS_\d+-\d+.xml.gz', r.text)
    result = tuple(match[0] for match in matches)
    print(f'[🔍] Discovered {len(result)} sitemaps')
    return result


@retry(timedelta(minutes=1))
async def download_and_analyze(sitemap_url: str) -> Sequence[tuple[str, str]]:
    async with _download_limiter:
        r = await HTTP.get(sitemap_url)
        r.raise_for_status()

    text = gzip.decompress(r.content).decode()
    result = []

    for match in re.finditer(r'/(?:(?P<locale>[\w-]+):)?(?P<page>(?:Key|Tag):.*?)</loc>', text):
        locale: str = match['locale'] or ''
        locale = unquote_plus(locale)

        # skip talk pages
        if locale.startswith(('Talk', 'Proposal')) or locale.endswith(('_talk', '_proposal')):
            continue

        page: str = match['page']
        page = unquote_plus(page)

        result.append((locale, page))

    print(f'[✅] {sitemap_url!r}: {len(result)} pages')
    return result


async def main():
    urls = await get_sitemap_links()
    locale_keys: list[tuple[str, str]] = []

    async def process_sitemap_url(sitemap_url: str):
        locale_keys.extend(await download_and_analyze(sitemap_url))

    async with create_task_group() as tg:
        for url in urls:
            tg.start_soon(process_sitemap_url, url)

    result: dict[str, set[str]] = defaultdict(set)

    for locale, key in locale_keys:
        result[key].add(locale)

    result_sorted = {k: sorted(v) for k, v in result.items()}
    buffer = json.dumps(result_sorted, indent=2, sort_keys=True)
    await _wiki_pages_path.write_text(buffer)


if __name__ == '__main__':
    anyio.run(main)
