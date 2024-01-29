import os
import pathlib

import anyio
import orjson
import yaml
from fastapi.utils import deep_dict_update
from tqdm import tqdm

from app.config import LOCALE_DIR

_download_dir = pathlib.Path(LOCALE_DIR / 'download')
_postprocess_dir = pathlib.Path(LOCALE_DIR / 'postprocess')
_locale_extra_en_path = pathlib.Path(LOCALE_DIR / 'extra_en.yaml')


def get_source_mtime(locale: str) -> float:
    source_path = _download_dir / f'{locale}.yaml'

    if locale == 'en':
        stat1 = source_path.stat()
        stat2 = _locale_extra_en_path.stat()
        return max(stat1.st_mtime, stat2.st_mtime)
    else:
        stat = source_path.stat()
        return stat.st_mtime


def needs_processing(locale: str) -> bool:
    source_path = _download_dir / f'{locale}.yaml'
    target_path = _postprocess_dir / f'{locale}.json'

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
    if translated := locale.get(community['id'], {}).get('name'):
        return translated

    # if not, then look up the default translated name for this type of community, and interpolate the template
    if (template := locale.get('_defaults', {}).get(community['type'], {}).get('name')) and (
        community_name := locale.get('_communities', {}).get(community['strings'].get('communityID'))
    ):
        template: str
        community_name: str
        return template.format(community=community_name)

    # otherwise fall back to the english resource name
    if translated := community['strings'].get('name'):
        return translated

    # finally use the english community name
    return community['strings']['community']


def extract_local_chapters_map() -> dict[str, dict]:
    """
    Returns a mapping of locale to locale overrides.
    """

    package_dir = pathlib.Path('node_modules/osm-community-index')
    resources = (package_dir / 'dist/resources.min.json').read_bytes()
    communities_dict: dict[str, dict] = orjson.loads(resources)['resources']

    # filter only local chapters
    communities = tuple(c for c in communities_dict.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')
    result = {}

    for source_path in tqdm(tuple((package_dir / 'i18n').glob('*.yaml')), desc='Processing local chapters'):
        locale = source_path.stem.replace('_', '-')

        if not needs_processing(locale):
            continue

        source_data: dict = yaml.load(source_path.read_bytes(), yaml.CSafeLoader)

        # strip first level of nesting
        source_data = next(iter(source_data.values()))

        communities_data = {}
        result[locale] = {'osm_community_index': {'communities': communities_data}}

        for community in communities:
            community_id: str = community['id']

            strings = source_data.get(community_id, {})
            strings['name'] = resolve_community_name(community, source_data)

            if community_id in communities_data:
                raise ValueError(f'Duplicate community id {community_id!r}')

            communities_data[community_id] = strings

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
            data[key] = value.replace('%{', '{')


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


def postprocess():
    local_chapters_map = extract_local_chapters_map()

    for source_path in tqdm(tuple(_download_dir.glob('*.yaml')), desc='Postprocessing'):
        locale = source_path.stem

        if not needs_processing(locale):
            continue

        data: dict = yaml.load(source_path.read_bytes(), yaml.CSafeLoader)

        # strip first level of nesting
        data = next(iter(data.values()))

        trim_values(data)
        convert_variable_format(data)
        convert_format_format(data)

        # apply local chapter overrides
        if local_chapters := local_chapters_map.get(locale):
            deep_dict_update(data, local_chapters)

        # apply extra overrides
        if locale == 'en' and (extra_data := yaml.load(_locale_extra_en_path.read_bytes(), yaml.CSafeLoader)):
            deep_dict_update(data, extra_data)

        buffer = orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        target_path = _postprocess_dir / f'{locale}.json'
        target_path.write_bytes(buffer)

        mtime = get_source_mtime(locale)
        os.utime(target_path, (mtime, mtime))


async def main():
    _postprocess_dir.mkdir(parents=True, exist_ok=True)
    postprocess()


if __name__ == '__main__':
    anyio.run(main, backend_options={'use_uvloop': True})
