import os
from hashlib import sha256
from pathlib import Path

import click
import orjson

_postprocess_dir = Path('config/locale/postprocess')
_i18next_dir = Path('config/locale/i18next')
_i18next_dir.mkdir(parents=True, exist_ok=True)
_i18next_map_path = _i18next_dir.joinpath('map.json')


def find_valid_output(locale: str, source_mtime: float) -> Path | None:
    target_iter = iter(p for p in _i18next_dir.glob(f'{locale}-*.js') if '-' not in p.stem[len(locale) + 1 :])
    target_path = next(target_iter, None)
    if target_path is None:
        return None
    if source_mtime > target_path.stat().st_mtime:
        # cleanup old files
        target_path.unlink()
        while (target_path := next(target_iter, None)) is not None:
            target_path.unlink()
        return None
    return target_path


@click.command()
def main() -> None:
    file_map: dict[str, str] = {}
    success_counter = 0
    for source_path in _postprocess_dir.glob('*.json'):
        locale = source_path.stem
        source_mtime = source_path.stat().st_mtime
        target_path = find_valid_output(locale, source_mtime)
        if target_path is not None:
            file_map[locale] = target_path.name
            continue

        # re-encode json to sort keys
        translation = orjson.dumps(orjson.loads(source_path.read_bytes()), option=orjson.OPT_SORT_KEYS)
        # transform json to javascript
        translation = f'if(!window.locales)window.locales={{}},window.locales["{locale}"]={{translation:{translation}}}'

        buffer = translation.encode()
        file_hash = sha256(buffer).hexdigest()[:16]
        file_name = f'{locale}-{file_hash}.js'
        target_path = _i18next_dir.joinpath(file_name)
        target_path.write_bytes(buffer)

        # preserve mtime
        os.utime(target_path, (source_mtime, source_mtime))
        file_map[locale] = file_name
        success_counter += 1

    if success_counter > 0:
        buffer = orjson.dumps(file_map, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE)
        _i18next_map_path.write_bytes(buffer)

    discover_str = click.style(f'{len(file_map)} locales', fg='green')
    success_str = click.style(f'{success_counter} locales', fg='bright_green')
    click.echo(f'[i18next] Discovered {discover_str}, transformed {success_str}')


if __name__ == '__main__':
    main()
