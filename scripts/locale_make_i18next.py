from hashlib import sha256
from os import utime
from pathlib import Path

import orjson

_POSTPROCESS_DIR = Path('config/locale/postprocess')
_I18NEXT_DIR = Path('config/locale/i18next')
_I18NEXT_DIR.mkdir(parents=True, exist_ok=True)
_I18NEXT_MAP_PATH = _I18NEXT_DIR.joinpath('map.json')


def find_valid_output(locale: str, effective_mtime: float) -> Path | None:
    target_iter = iter(
        p
        for p in _I18NEXT_DIR.glob(f'{locale}-*.js')
        if '-' not in p.stem[len(locale) + 1 :]
    )
    target_path = next(target_iter, None)
    if target_path is None:
        return None

    # cleanup old files
    if effective_mtime > target_path.stat().st_mtime:
        target_path.unlink()
        while (target_path := next(target_iter, None)) is not None:
            target_path.unlink()
        return None

    return target_path


def main() -> None:
    script_mtime = Path(__file__).stat().st_mtime
    file_map: dict[str, str] = {}
    success_counter = 0

    for source_path in _POSTPROCESS_DIR.glob('*.json'):
        locale = source_path.stem
        source_mtime = source_path.stat().st_mtime
        effective_mtime = max(source_mtime, script_mtime)
        target_path = find_valid_output(locale, effective_mtime)
        if target_path is not None:
            file_map[locale] = target_path.name
            continue

        # re-encode json to sort keys
        translation = orjson.dumps(
            orjson.loads(source_path.read_bytes()),
            option=orjson.OPT_SORT_KEYS,
        ).decode()
        # transform json to javascript
        translation = f'if(!window.locales)window.locales={{}};window.locales["{locale}"]={{translation:{translation}}}'

        buffer = translation.encode()
        file_hash = sha256(buffer).hexdigest()[:16]
        file_name = f'{locale}-{file_hash}.js'
        target_path = _I18NEXT_DIR.joinpath(file_name)
        target_path.write_bytes(buffer)

        # preserve mtime
        utime(target_path, (effective_mtime, effective_mtime))
        file_map[locale] = file_name
        success_counter += 1

    if success_counter:
        buffer = orjson.dumps(
            file_map,
            option=(
                orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE
            ),
        )
        _I18NEXT_MAP_PATH.write_bytes(buffer)

    print(
        f'[i18next] Discovered {len(file_map)} locales, '
        f'transformed {success_counter} locales'
    )


if __name__ == '__main__':
    main()
