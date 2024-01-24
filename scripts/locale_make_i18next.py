from hashlib import sha256

import anyio
import orjson

from app.config import LOCALE_DIR

_postprocess_dir = LOCALE_DIR / 'postprocess'
_out_dir = LOCALE_DIR / 'i18next'


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


async def convert_style():
    async for path in _postprocess_dir.glob('*.json'):
        locale = path.stem
        data = orjson.loads(await path.read_bytes())

        convert_variable_format(data)
        convert_plural_format(data)

        buffer = orjson.dumps(
            data,
            option=orjson.OPT_SORT_KEYS,
        )

        file_hash = sha256(buffer).hexdigest()[:16]
        file_name = f'{locale}-{file_hash}.json'

        await (_out_dir / file_name).write_bytes(buffer)
        print(f'[✅] {locale!r}: saved as {file_name!r}')


async def main():
    await _out_dir.mkdir(parents=True, exist_ok=True)
    await convert_style()


if __name__ == '__main__':
    anyio.run(main)
