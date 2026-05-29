from hashlib import sha256
from os import utime
from pathlib import Path

import orjson
import re2

_POSTPROCESS_DIR = Path('config/locale/postprocess')
_I18NEXT_DIR = Path('config/locale/i18next')
_I18NEXT_DIR.mkdir(parents=True, exist_ok=True)
_I18NEXT_MAP_PATH = _I18NEXT_DIR.joinpath('map.json')

# Escape hatch for include-prefixes that cannot be reached from the
# auto-detected template-literal pattern `t(`prefix.${...}`)` in TS/TSX
# sources. Prefer refactoring the call site so the prefix is visible to the
# extractor (see app/views/user/profile/_edit-modals.tsx for an example)
# before adding entries here. Entries are validated against en.json at build
# time and must resolve to a non-empty subtree.
_EXTRA_INCLUDE_PREFIXES: list[str] = []

# i18next plural suffixes to strip when matching used keys
_PLURAL_SUFFIXES = ('_zero', '_one', '_two', '_few', '_many', '_other')

# Match i18next.t() / t() / tRich() calls with a literal first argument.
# Group 1: "double-quoted" key.  Group 2: 'single-quoted' key.
# Group 3: `template literal` content, possibly containing ${...}; we
# post-process this to extract either a literal key (no interpolation) or a
# static prefix ending in '.' (the part before the first ${).
_FIND_USED_KEYS_OPTIONS = re2.Options()
_FIND_USED_KEYS_OPTIONS.dot_nl = True
_FIND_USED_KEYS_RE = re2.compile(
    r'(?:\bi18next\.t|(?:^|[^.\w])(?:t|tRich))\s*\(\s*'
    r'(?:"((?:\\.|[^"\\])*)"'
    r"|'((?:\\.|[^'\\])*)'"
    r'|`([^`]*)`)'
    r'\s*[,)]',
    _FIND_USED_KEYS_OPTIONS,
)


def find_used_keys():
    """Extract translation keys and dynamic prefixes used in the source files.

    Returns (used_keys, prefixes, mtime). Prefixes are dot-terminated and cover
    every key under that namespace (e.g. 'service.' covers 'service.github.title').
    """
    used_keys: set[str] = set()
    prefixes: set[str] = set()
    mtime = 0

    for source in (
        source
        for ext in ('.ts', '.tsx')
        for source in Path('app/views').rglob(f'*{ext}')
    ):
        found = False
        for match in _FIND_USED_KEYS_RE.finditer(source.read_text()):
            found = True
            if (key := match[1]) is not None or (key := match[2]) is not None:
                if key:
                    used_keys.add(key)
            elif (template := match[3]) is not None:
                interp = template.find('${')
                if interp < 0:
                    if template:
                        used_keys.add(template)
                else:
                    static = template[:interp]
                    if static.endswith('.'):
                        prefixes.add(static)
        if found:
            mtime = max(mtime, source.stat().st_mtime)

    return used_keys, prefixes, mtime


def validate_prefixes(prefixes: set[str], en_data: dict):
    """Assert every prefix resolves to a non-empty subtree in en.json.

    Catches both stale escape-hatch entries and typos in dynamic `t(`...${}`)`
    calls (the path simply won't exist in the locale data).
    """
    errors: list[str] = []
    for prefix in sorted(prefixes):
        node = en_data
        for part in prefix.rstrip('.').split('.'):
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if not isinstance(node, dict):
            errors.append(
                f'  {prefix!r}: path missing or resolves to a leaf in en.json'
            )
        elif not node:
            errors.append(f'  {prefix!r}: resolves to an empty subtree')
    if errors:
        raise RuntimeError(
            'i18n prefix validation failed:\n'
            + '\n'.join(errors)
            + '\n(refactor the source to a literal `t(`prefix.${...}`)` call'
            ' or remove the stale _EXTRA_INCLUDE_PREFIXES entry)'
        )


def filter_unused_keys(
    obj: dict,
    used_keys: set[str],
    prefixes_dot: tuple[str, ...],
    *,
    _parent_path: str = '',
):
    """Filter translation dictionary by used keys."""
    filtered = {}

    for key, value in obj.items():
        current_path = f'{_parent_path}.{key}' if _parent_path else key

        # Recursively filter nested dictionaries
        if isinstance(value, dict):
            if filtered_nested := filter_unused_keys(
                value, used_keys, prefixes_dot, _parent_path=current_path
            ):
                filtered[key] = filtered_nested
        # Check if this key should be included
        else:
            # Strip plural suffix from path to match base key in used_keys
            candidate = current_path
            if current_path.endswith(_PLURAL_SUFFIXES):
                for suffix in _PLURAL_SUFFIXES:
                    if current_path.endswith(suffix):
                        candidate = current_path[: -len(suffix)]
                        break

            if candidate in used_keys or current_path.startswith(prefixes_dot):
                filtered[key] = value

    return filtered


def find_valid_output(locale: str, effective_mtime: float):
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


def main():
    script_mtime = Path(__file__).stat().st_mtime
    file_map: dict[str, str] = {}
    transform_count = 0

    used_keys, detected_prefixes, used_keys_mtime = find_used_keys()
    all_prefixes = detected_prefixes | {
        f'{p.rstrip(".")}.' for p in _EXTRA_INCLUDE_PREFIXES
    }
    prefixes_dot = tuple(sorted(all_prefixes))
    # `used_keys` already lists every prefix anchor we want preserved at the
    # leaf level (e.g. `service` itself, alongside `service.*` descendants).
    combined_keys = used_keys | {p.rstrip('.') for p in all_prefixes}
    original_keys_count = 0
    filtered_keys_count = 0

    en_path = _POSTPROCESS_DIR / 'en.json'
    if en_path.is_file():
        validate_prefixes(all_prefixes, orjson.loads(en_path.read_bytes()))

    for source_path in _POSTPROCESS_DIR.glob('*.json'):
        locale = source_path.stem
        source_mtime = source_path.stat().st_mtime
        effective_mtime = max(source_mtime, script_mtime, used_keys_mtime)
        target_path = find_valid_output(locale, effective_mtime)
        if target_path is not None:
            file_map[locale] = target_path.name
            continue

        def count_keys(obj: dict):
            count = len(obj)
            for value in obj.values():
                if isinstance(value, dict):
                    count += count_keys(value) - 1
            return count

        # Load and filter translation data
        translation_data = orjson.loads(source_path.read_bytes())
        if locale == 'en':
            original_keys_count = count_keys(translation_data)
        translation_data = filter_unused_keys(
            translation_data, combined_keys, prefixes_dot
        )
        if locale == 'en':
            filtered_keys_count = count_keys(translation_data)

        # Re-encode json to sort keys
        translation = orjson.dumps(
            translation_data,
            option=orjson.OPT_SORT_KEYS,
        )

        # Transform to javascript
        buffer = b''.join((
            b'if(!window.locales)window.locales={};window.locales["',
            locale.encode(),
            b'"]={translation:',
            translation,
            b'}',
        ))

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
        f'[i18next] Source analysis found {len(used_keys)} used keys, '
        f'{len(detected_prefixes)} dynamic prefixes',
    )
    for prefix in sorted(detected_prefixes):
        print(f'[i18next]   prefix: {prefix.rstrip(".")}.*')
    if original_keys_count:
        print(
            f'[i18next] Filtered {original_keys_count} → {filtered_keys_count} keys '
            f'({(original_keys_count - filtered_keys_count) / original_keys_count * 100:.1f}% smaller)'
        )


if __name__ == '__main__':
    main()
