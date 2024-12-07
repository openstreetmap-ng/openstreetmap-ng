import os
from collections.abc import Collection, Mapping, MutableMapping
from pathlib import Path
from typing import Any

import click
import orjson
import yaml

_oci_dir = Path('node_modules/osm-community-index')
_download_dir = Path('config/locale/download')
_postprocess_dir = Path('config/locale/postprocess')
_postprocess_dir.mkdir(parents=True, exist_ok=True)
_locale_extra_en_path = Path('config/locale/extra_en.yaml')


def get_source_mtime(locale: str) -> float:
    source_path = _download_dir.joinpath(f'{locale}.yaml')
    source_mtime = source_path.stat().st_mtime
    return source_mtime if (locale != 'en') else max(source_mtime, _locale_extra_en_path.stat().st_mtime)


def needs_processing(locale: str, source_mtime: float) -> bool:
    source_path = _download_dir.joinpath(f'{locale}.yaml')
    target_path = _postprocess_dir.joinpath(f'{locale}.json')
    if not source_path.is_file():
        return False
    if not target_path.is_file():
        return True
    return source_mtime > target_path.stat().st_mtime


def resolve_community_name(community: dict[str, Any], locale: dict[str, Any]) -> str:
    """
    Resolve the localized name for a community.
    """
    # if theres an explicitly translated name then use that
    if (translated := locale.get(community['id'], {}).get('name')) is not None:
        return translated

    # if not, then look up the default translated name for this type of community
    if (community_name := locale.get('_communities', {}).get(community['strings'].get('communityID'))) is not None:
        # and optionally interpolate the template
        if (template := locale.get('_defaults', {}).get(community['type'], {}).get('name')) is not None:
            try:
                # workaround around broken templates
                # https://github.com/osmlab/osm-community-index/issues/739
                return template.format(community=community_name)
            except KeyError:
                pass
        return community_name

    # otherwise fall back to the english resource name
    if (translated := community['strings'].get('name')) is not None:
        return translated

    # finally use the english community name
    return community['strings']['community']


class LocalChaptersExtractor:
    def __init__(self) -> None:
        resources = (_oci_dir.joinpath('dist/resources.min.json')).read_bytes()
        communities_dict: dict[str, dict[str, Any]] = orjson.loads(resources)['resources']

        # filter only local chapters
        self.communities = tuple(c for c in communities_dict.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')

    def extract(self, locale: str) -> dict:
        source_path = _oci_dir.joinpath(f'i18n/{locale.replace('-', '_')}.yaml')
        if not source_path.is_file():
            return {}

        source_data: dict[str, Any] = yaml.load(source_path.read_bytes(), yaml.CSafeLoader)
        source_data = next(iter(source_data.values()))  # strip first level of nesting

        communities_data: dict[str, dict[str, Any]] = {}
        for community in self.communities:
            community_id: str = community['id']
            strings = source_data.get(community_id, {})
            strings['name'] = resolve_community_name(community, source_data)

            if community_id in communities_data:
                raise ValueError(f'Duplicate community id {community_id!r}')

            communities_data[community_id] = strings

        return {'osm_community_index': {'communities': communities_data}}


@click.command()
@click.option('--verbose', '-v', is_flag=True)
def main(verbose: bool):
    lc_extractor = LocalChaptersExtractor()
    if verbose:
        click.echo([c['id'] for c in lc_extractor.communities])

    discover_counter = 0
    success_counter = 0
    for source_path in _download_dir.glob('*.yaml'):
        discover_counter += 1
        locale = source_path.stem
        source_mtime = get_source_mtime(locale)
        if not needs_processing(locale, source_mtime):
            continue

        data: dict = yaml.load(source_path.read_bytes(), yaml.CSafeLoader)
        data = next(iter(data.values()))  # strip first level of nesting

        trim_values(data)
        convert_placeholder_format(data)
        convert_number_format(data)
        convert_plural_structure(data)
        rename_buggy_keys(data)

        # merge local chapters
        deep_dict_update(data, lc_extractor.extract(locale))

        # merge extra_ data
        if locale == 'en' and (extra_data := yaml.load(_locale_extra_en_path.read_bytes(), yaml.CSafeLoader)):
            deep_dict_update(data, extra_data)

        buffer = orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE)
        target_path = _postprocess_dir.joinpath(f'{locale}.json')
        target_path.write_bytes(buffer)

        # preserve mtime
        os.utime(target_path, (source_mtime, source_mtime))
        success_counter += 1

    discover_str = click.style(f'{discover_counter} locales', fg='green')
    success_str = click.style(f'{success_counter} locales', fg='bright_green')
    lc_str = click.style(f'{len(lc_extractor.communities)} local chapters', fg='green')
    click.echo(f'Discovered {discover_str} and {lc_str}, postprocessed {success_str}')


def trim_values(data: dict):
    """
    Trim all string values.
    """
    for key, value in data.items():
        if isinstance(value, dict):
            trim_values(value)
        elif isinstance(value, str):
            value = value.strip()
            while value.startswith('\\n'):
                value = value[2:]
            while value.endswith('\\n'):
                value = value[:-2]
            data[key] = value.strip()


def convert_placeholder_format(data: dict):
    """
    Convert %{placeholder} to {placeholder} in all strings.
    """
    for key, value in data.items():
        if isinstance(value, dict):
            convert_placeholder_format(value)
        elif isinstance(value, str):
            data[key] = value.replace('%{', '{{').replace('}', '}}')


def convert_number_format(data: dict):
    """
    Convert %e to %-d in all strings.
    """
    # backwards compatibility: remove leading zero from day
    for key, value in data.items():
        if isinstance(value, dict):
            convert_number_format(value)
        elif isinstance(value, str):
            data[key] = value.replace('%e', '%-d')


def convert_plural_structure(data: dict):
    """
    Convert plural dicts to singular keys.

    >>> convert_plural_structure({'example': {'one': '1', 'two': '2', 'three': '3'}})
    {'example_one': '1', 'example_two': '2', 'example_three': '3'}
    """
    for k, v in tuple(data.items()):
        # skip non-dict values
        if not isinstance(v, dict):
            continue

        # recurse non-plural dicts
        if any(v_key not in {'zero', 'one', 'two', 'few', 'many', 'other'} for v_key in v):
            convert_plural_structure(v)
            continue

        # convert plural dicts
        for count, value in v.items():
            data[f'{k}_{count}'] = value

        # remove the original plural dict
        data.pop(k)


def rename_buggy_keys(data: dict):
    """
    Rename keys that bug-out during i18next -> gnu conversion.

    >>> rename_buggy_keys({'some_other': 'value'})
    {'some other': 'value'}
    """
    buggy_keys = []
    abort = False
    for k, v in tuple(data.items()):
        if isinstance(v, dict):
            rename_buggy_keys(v)
            continue

        suffix = k.rsplit('_', 1)[-1]
        if suffix == 'other':
            buggy_keys.append(k)
        elif suffix in {'zero', 'one', 'two', 'few', 'many'}:
            abort = True
    if abort:
        return
    for k in buggy_keys:
        k_alt = k.replace('_other', ' other')
        data[k_alt] = data[k]


def deep_dict_update(d: MutableMapping, u: Mapping) -> None:
    for k, uv in u.items():
        dv = d.get(k)
        if dv is None:
            d[k] = uv
        elif isinstance(dv, MutableMapping) and isinstance(uv, Mapping):
            deep_dict_update(dv, uv)
        elif isinstance(dv, Collection) and isinstance(uv, Collection):
            d[k] = [*dv, *uv]
        else:
            d[k] = uv


if __name__ == '__main__':
    main()
