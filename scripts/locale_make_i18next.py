import re
from hashlib import sha256
from os import utime
from pathlib import Path

import orjson

_POSTPROCESS_DIR = Path('config/locale/postprocess')
_I18NEXT_DIR = Path('config/locale/i18next')
_I18NEXT_DIR.mkdir(parents=True, exist_ok=True)
_I18NEXT_MAP_PATH = _I18NEXT_DIR.joinpath('map.json')

_INCLUDE_PREFIXES = [
    'javascripts.key.tooltip',
    'javascripts.key.tooltip_disabled',
    'javascripts.map.layers.title',
    'javascripts.share.title',
]

_INCLUDE_PREFIXES_DOT = [f'{prefix}.' for prefix in _INCLUDE_PREFIXES]


def find_used_keys() -> set[str]:
    """Extract translation keys used in the source files."""
    # Regex patterns to match i18next.t() and t() calls with literal strings
    patterns = [
        re.compile(
            r'\bi18next\.t\s*\(\s*(["\'])(?P<key>(?:\\.|(?!\1).)*)\1\s*[,)]', re.DOTALL
        ),
        re.compile(
            r'(?<![.\w])t\s*\(\s*(["\'])(?P<key>(?:\\.|(?!\1).)*)\1\s*[,)]', re.DOTALL
        ),
    ]

    return {
        match['key']
        for source in Path('app/views').rglob('*.ts')
        if (content := source.read_text())
        for pattern in patterns
        for match in pattern.finditer(content)
    }


def filter_unused_keys(
    obj: dict, used_keys: set[str], *, _parent_path: str = ''
) -> dict:
    """Filter translation dictionary by used keys."""
    filtered = {}

    for key, value in obj.items():
        current_path = f'{_parent_path}.{key}' if _parent_path else key

        # Recursively filter nested dictionaries
        if isinstance(value, dict):
            if filtered_nested := filter_unused_keys(
                value, used_keys, _parent_path=current_path
            ):
                filtered[key] = filtered_nested
        # Check if this key should be included
        elif current_path in used_keys or any(
            current_path.startswith(prefix) for prefix in _INCLUDE_PREFIXES_DOT
        ):
            filtered[key] = value

    return filtered


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
    transform_count = 0

    used_keys = find_used_keys()
    combined_keys = used_keys.copy()
    combined_keys.update(_INCLUDE_PREFIXES)
    original_keys_count = 0
    filtered_keys_count = 0

    for source_path in _POSTPROCESS_DIR.glob('*.json'):
        locale = source_path.stem
        source_mtime = source_path.stat().st_mtime
        effective_mtime = max(source_mtime, script_mtime)
        target_path = find_valid_output(locale, effective_mtime)
        if target_path is not None:
            file_map[locale] = target_path.name
            continue

        def count_keys(obj: dict) -> int:
            count = len(obj)
            for value in obj.values():
                if isinstance(value, dict):
                    count += count_keys(value) - 1
            return count

        # Load and filter translation data
        translation_data = orjson.loads(source_path.read_bytes())
        if locale == 'en':
            original_keys_count = count_keys(translation_data)
        translation_data = filter_unused_keys(translation_data, combined_keys)
        if locale == 'en':
            filtered_keys_count = count_keys(translation_data)

        # Re-encode json to sort keys
        translation = orjson.dumps(
            translation_data,
            option=orjson.OPT_SORT_KEYS,
        ).decode()

        # Transform to javascript
        translation = f'if(!window.locales)window.locales={{}};window.locales["{locale}"]={{translation:{translation}}}'

        buffer = translation.encode()
        file_hash = sha256(buffer).hexdigest()[:16]
        file_name = f'{locale}-{file_hash}.js'
        target_path = _I18NEXT_DIR.joinpath(file_name)
        target_path.write_bytes(buffer)

        # Preserve mtime
        utime(target_path, (effective_mtime, effective_mtime))
        file_map[locale] = file_name
        transform_count += 1

    if transform_count:
        buffer = orjson.dumps(
            file_map,
            option=(
                orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE
            ),
        )
        _I18NEXT_MAP_PATH.write_bytes(buffer)

    print(
        f'[i18next] Discovered {len(file_map)} locales, '
        f'transformed {transform_count} locales'
    )
    print(
        f'[i18next] Source analysis found {len(used_keys)} used keys',
    )
    print(
        f'[i18next] Filtered {original_keys_count} → {filtered_keys_count} keys '
        f'({(original_keys_count - filtered_keys_count) / original_keys_count * 100:.1f}% reduction)'
    )


if __name__ == '__main__':
    main()
