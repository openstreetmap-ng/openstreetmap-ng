import os
import pathlib
from hashlib import sha256

import anyio
import orjson
from tqdm import tqdm

from app.config import LOCALE_DIR

_postprocess_dir = pathlib.Path(LOCALE_DIR / 'postprocess')
_i18next_dir = pathlib.Path(LOCALE_DIR / 'i18next')


def convert() -> dict[str, str]:
    file_map = {}

    for source_path in tqdm(tuple(_postprocess_dir.glob('*.json')), desc='Converting to JavaScript'):
        locale = source_path.stem

        data = orjson.loads(source_path.read_bytes())
        buffer = orjson.dumps(data, option=orjson.OPT_SORT_KEYS).decode()
        buffer = f'if(!window.locales)window.locales={{}},window.locales["{locale}"]={{translation:{buffer}}}'
        buffer = buffer.encode()

        file_hash = sha256(buffer).hexdigest()[:16]
        file_name = f'{locale}-{file_hash}.js'
        target_path = _i18next_dir / file_name
        target_path.write_bytes(buffer)

        stat = source_path.stat()
        os.utime(target_path, (stat.st_atime, stat.st_mtime))

        file_map[locale] = file_name

    return file_map


async def main():
    _i18next_dir.mkdir(parents=True, exist_ok=True)
    file_map = convert()

    output = orjson.dumps(file_map, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    output_path = _i18next_dir / 'map.json'
    output_path.write_bytes(output)


if __name__ == '__main__':
    anyio.run(main, backend_options={'use_uvloop': True})
