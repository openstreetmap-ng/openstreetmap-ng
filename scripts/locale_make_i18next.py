import os
import pathlib
from hashlib import sha256

import anyio
import orjson
from tqdm import tqdm

from app.config import LOCALE_DIR

_postprocess_dir = pathlib.Path(LOCALE_DIR / 'postprocess')
_i18next_dir = pathlib.Path(LOCALE_DIR / 'i18next')


def convert_variable_format(data: dict):
    """
    Convert {variable} to {{variable}} in all strings.
    """

    for key, value in data.items():
        if isinstance(value, dict):
            convert_variable_format(value)
        elif isinstance(value, str):
            data[key] = value.replace('{', '{{').replace('}', '}}')


def convert_plural_format(data: dict):
    """
    Convert plural dicts to singular keys.
    """

    # {'example': {'one': 'one', 'two': 'two', 'three': 'three'}}
    # to:
    # {'example_one': 'one', 'example_two': 'two', 'example_three': 'three'}

    for k, v in tuple(data.items()):
        # skip non-dict values
        if not isinstance(v, dict):
            continue

        # recurse non-plural dicts
        if not any(count in v for count in ('zero', 'one', 'two', 'few', 'many', 'other')):
            convert_plural_format(v)
            continue

        # convert plural dicts
        for count, value in v.items():
            data[f'{k}_{count}'] = value

        # remove the original plural dict
        data.pop(k)


def convert():
    for source_path in tqdm(tuple(_postprocess_dir.glob('*.json')), desc='Converting to i18next format'):
        locale = source_path.stem

        data = orjson.loads(source_path.read_bytes())

        convert_variable_format(data)
        convert_plural_format(data)

        buffer = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)

        file_hash = sha256(buffer).hexdigest()[:16]
        file_name = f'{locale}-{file_hash}.json'
        target_path = _i18next_dir / file_name
        target_path.write_bytes(buffer)

        stat = source_path.stat()
        os.utime(target_path, (stat.st_atime, stat.st_mtime))


async def main():
    _i18next_dir.mkdir(parents=True, exist_ok=True)
    convert()


if __name__ == '__main__':
    anyio.run(main, backend_options={'use_uvloop': True})
