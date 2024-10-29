import json
import tomllib
from asyncio import Semaphore, Task, TaskGroup
from datetime import timedelta
from pathlib import Path

import uvloop

from app.lib.retry import retry
from app.utils import HTTP, JSON_DECODE

_download_limiter = Semaphore(6)  # max concurrent downloads

# _config[key][value] = icon
# _config[key.type][value] = icon
_config = tomllib.loads(Path('config/feature_icons.toml').read_text())
_output_path = Path('config/feature_icons_popular.json')


@retry(timedelta(minutes=1))
async def get_popularity(key: str, type: str, value: str) -> float:
    if value == '*':
        url = 'https://taginfo.openstreetmap.org/api/4/key/stats'
        params = {'key': key}
    else:
        url = 'https://taginfo.openstreetmap.org/api/4/tag/stats'
        params = {'key': key, 'value': value}

    async with _download_limiter:
        r = await HTTP.get(url, params=params)
        r.raise_for_status()
        data = JSON_DECODE(r.content)['data']

    return sum(item['count'] for item in data if not type or item['type'].startswith(type))


async def main():
    async with TaskGroup() as tg:
        tasks: list[tuple[tuple, Task]] = []
        for key_orig, values in _config.items():
            key, _, type = key_orig.partition('.')
            tasks.extend(
                ((key_orig, value), tg.create_task(get_popularity(key, type, value)))
                for value in values  #
            )

    for (key_orig, value), task in tasks:
        _config[key_orig][value] = task.result()

    buffer = json.dumps(_config, indent=2, sort_keys=True) + '\n'
    _output_path.write_text(buffer)


if __name__ == '__main__':
    uvloop.run(main())
