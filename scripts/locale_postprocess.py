import json
import os
from pathlib import Path

import yaml
from fastapi.utils import deep_dict_update
from tqdm import tqdm

_download_dir = Path('config/locale/download')
_postprocess_dir = Path('config/locale/postprocess')
_locale_extra_en_path = Path('config/locale/extra_en.yaml')


def get_source_mtime(locale: str) -> float:
    source_path = _download_dir.joinpath(f'{locale}.yaml')
    if locale == 'en':
        stat1 = source_path.stat()
        stat2 = _locale_extra_en_path.stat()
        return max(stat1.st_mtime, stat2.st_mtime)
    else:
        stat = source_path.stat()
        return stat.st_mtime


def needs_processing(locale: str) -> bool:
    source_path = _download_dir.joinpath(f'{locale}.yaml')
    target_path = _postprocess_dir.joinpath(f'{locale}.json')
    if not source_path.is_file():
        return False
    if not target_path.is_file():
        return True
    return get_source_mtime(locale) > target_path.stat().st_mtime


def resolve_community_name(community: dict, locale: dict) -> str:
    """
    Resolve the translated name for a community.
    """
    # if theres an explicitly translated name then use that
    if (translated := locale.get(community['id'], {}).get('name')) is not None:
        return translated

    # if not, then look up the default translated name for this type of community, and interpolate the template
    if (template := locale.get('_defaults', {}).get(community['type'], {}).get('name')) is not None:  # noqa: SIM102
        if (community_name := locale.get('_communities', {}).get(community['strings'].get('communityID'))) is not None:
            return template.format(community=community_name)

    # otherwise fall back to the english resource name
    if (translated := community['strings'].get('name')) is not None:
        return translated

    # finally use the english community name
    return community['strings']['community']


def extract_local_chapters_map() -> dict[str, dict]:
    """
    Returns a mapping of locale to locale overrides.
    """
    package_dir = Path('node_modules/osm-community-index')
    resources = (package_dir.joinpath('dist/resources.min.json')).read_bytes()
    communities_dict: dict[str, dict] = json.loads(resources)['resources']

    # filter only local chapters
    communities = tuple(c for c in communities_dict.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')
    result = {}

    for source_path in tqdm(tuple((package_dir / 'i18n').glob('*.yaml')), desc='Processing local chapters'):
        locale = source_path.stem.replace('_', '-')
        if not needs_processing(locale):
            continue

        source_data: dict = yaml.load(source_path.read_bytes(), yaml.CSafeLoader)
        source_data = next(iter(source_data.values()))  # strip first level of nesting

        communities_data: dict[str, dict] = {}
        for community in communities:
            community_id: str = community['id']

            strings = source_data.get(community_id, {})
            strings['name'] = resolve_community_name(community, source_data)

            if community_id in communities_data:
                raise ValueError(f'Duplicate community id {community_id!r}')

            communities_data[community_id] = strings

        result[locale] = {'osm_community_index': {'communities': communities_data}}

    return result


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


def convert_variable_format(data: dict):
    """
    Convert %{variable} to {variable} in all strings.
    """
    for key, value in data.items():
        if isinstance(value, dict):
            convert_variable_format(value)
        elif isinstance(value, str):
            data[key] = value.replace('%{', '{{').replace('}', '}}')


def convert_format_format(data: dict):
    """
    Convert %e to %-d in all strings.
    """
    # backwards compatibility: remove leading zero from day
    for key, value in data.items():
        if isinstance(value, dict):
            convert_format_format(value)
        elif isinstance(value, str):
            data[key] = value.replace('%e', '%-d')


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
        if any(v_key not in ('zero', 'one', 'two', 'few', 'many', 'other') for v_key in v):
            convert_plural_format(v)
            continue

        # convert plural dicts
        for count, value in v.items():
            data[f'{k}_{count}'] = value

        # remove the original plural dict
        data.pop(k)


def postprocess():
    local_chapters_map = extract_local_chapters_map()

    for source_path in tqdm(tuple(_download_dir.glob('*.yaml')), desc='Postprocessing'):
        locale = source_path.stem
        if not needs_processing(locale):
            continue

        data: dict = yaml.load(source_path.read_bytes(), yaml.CSafeLoader)
        data = next(iter(data.values()))  # strip first level of nesting

        trim_values(data)
        convert_variable_format(data)
        convert_format_format(data)
        convert_plural_format(data)

        # apply local chapter overrides
        if (local_chapters := local_chapters_map.get(locale)) is not None:
            deep_dict_update(data, local_chapters)

        # apply extra overrides
        if locale == 'en' and (extra_data := yaml.load(_locale_extra_en_path.read_bytes(), yaml.CSafeLoader)):
            deep_dict_update(data, extra_data)

        buffer = json.dumps(data, indent=2, sort_keys=True)
        target_path = _postprocess_dir.joinpath(f'{locale}.json')
        target_path.write_text(buffer)

        mtime = get_source_mtime(locale)
        os.utime(target_path, (mtime, mtime))


def main():
    _postprocess_dir.mkdir(parents=True, exist_ok=True)
    postprocess()


if __name__ == '__main__':
    main()
