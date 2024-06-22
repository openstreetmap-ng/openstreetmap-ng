import json
import pathlib
import tomllib
from datetime import timedelta

import anyio
from anyio import CapacityLimiter, create_task_group

from app.config import CONFIG_DIR
from app.lib.retry import retry
from app.utils import HTTP

_download_limiter = CapacityLimiter(6)  # max concurrent downloads

# _config[tag_key][tag_value] = icon
# _config[tag_key][type][tag_value] = icon
_config = tomllib.loads(pathlib.Path(CONFIG_DIR / 'feature_icons.toml').read_text())
_output_path = CONFIG_DIR / 'feature_icons_popular.json'


@retry(timedelta(minutes=1))
async def get_popularity(key: str, value: str, type: str) -> float:
    if value == '*':
        url = 'https://taginfo.openstreetmap.org/api/4/key/stats'
        params = {'key': key}
    else:
        url = 'https://taginfo.openstreetmap.org/api/4/tag/stats'
        params = {'key': key, 'value': value}

    async with _download_limiter:
        r = await HTTP.get(url, params=params)
        r.raise_for_status()

    data = r.json()['data']
    return sum(item['count'] for item in data if not type or item['type'].startswith(type))


async def main():
    popularity: dict[tuple[str, str], int] = {}

    async def task(key: str, value: str, type: str):
        popularity[(key, value, type)] = await get_popularity(key, value, type)

    async with create_task_group() as tg:
        for key, values in _config.items():
            key, _, type = key.partition('.')
            for value in values:
                tg.start_soon(task, key, value, type)

    for key_orig, values in _config.items():
        key, _, type = key_orig.partition('.')
        for value in values:
            _config[key_orig][value] = popularity[(key, value, type)]

    buffer = json.dumps(_config, indent=2, sort_keys=True) + '\n'
    await _output_path.write_text(buffer)


if __name__ == '__main__':
    anyio.run(main)
