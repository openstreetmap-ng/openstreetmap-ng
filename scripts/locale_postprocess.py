import pathlib

import anyio
import orjson
import yaml
from anyio import Path

from app.config import LOCALE_DIR

_download_dir = LOCALE_DIR / 'download'
_postprocess_dir = LOCALE_DIR / 'postprocess'


def convert_variable_format(data: dict) -> dict:
    """
    Convert %{variable} to {variable} in all strings.
    """

    for key, value in data.items():
        if isinstance(value, dict):
            convert_variable_format(value)
        elif isinstance(value, str):
            data[key] = value.replace('%{', '{')


async def convert_yaml_to_json():
    async for path in _download_dir.glob('*.yaml'):
        with pathlib.Path(path).open('rb') as f:
            data = yaml.safe_load(f)

        # strip first level of nesting
        data = next(iter(data.values()))

        convert_variable_format(data)

        await (_postprocess_dir / f'{path.stem}.json').write_bytes(
            orjson.dumps(
                data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
            )
        )
        print(f'[✅] {path.stem!r}: converted to json')


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


async def extend_local_chapters():
    package_dir = Path('node_modules/osm-community-index')
    resources = await (package_dir / 'dist/resources.min.json').read_bytes()
    communities_dict: dict[str, dict] = orjson.loads(resources)['resources']

    # filter only local chapters
    communities = tuple(c for c in communities_dict.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')

    async for locale_path in (package_dir / 'i18n').glob('*.yaml'):
        locale_name = locale_path.stem.replace('_', '-')
        postprocess_locale_path = _postprocess_dir / f'{locale_name}.json'

        if not await postprocess_locale_path.is_file():
            print(f'[❔] {locale_name!r}: missing postprocess file')
            continue

        with pathlib.Path(locale_path).open('rb') as f:
            locale_data: dict = yaml.safe_load(f)

        postprocess_data: dict = orjson.loads(await postprocess_locale_path.read_bytes())
        postprocess_data.setdefault('osm_community_index', {})
        postprocess_data['osm_community_index'].setdefault('communities', {})
        communities_data = postprocess_data['osm_community_index']['communities']

        for community in communities:
            community_id: str = community['id']
            strings = locale_data.get(community_id, {})
            strings['name'] = resolve_community_name(community, locale_data)

            if community_id in communities_data:
                raise ValueError(f'Duplicate community id {community_id!r}')

            communities_data[community_id] = strings

        await postprocess_locale_path.write_bytes(
            orjson.dumps(
                postprocess_data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
            )
        )
        print(f'[✅] {locale_name!r}: extended {len(communities)} local chapters')


async def main():
    await _postprocess_dir.mkdir(parents=True, exist_ok=True)
    await convert_yaml_to_json()
    await extend_local_chapters()


if __name__ == '__main__':
    anyio.run(main)
