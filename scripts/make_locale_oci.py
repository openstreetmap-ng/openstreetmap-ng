import json
from collections.abc import Mapping
from pathlib import Path

import yaml


def flatten(data: dict, parent_key: str = '', separator: str = '.') -> dict:
    """
    Flatten a nested dictionary into a single level, using the given separator.

    >>> flatten({'a': {'b': 1, 'c': 2}})
    {'a.b': 1, 'a.c': 2}
    """

    items = {}

    for k, v in data.items():
        new_key = f'{parent_key}{separator}{k}' if parent_key else k
        if isinstance(v, Mapping):
            items.update(flatten(v, new_key, separator=separator))
        else:
            items[new_key] = v

    return items


def resolve_name(community: dict, locale: dict) -> str:
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
        return template.format(community=community_name)

    # otherwise fall back to the English resource name
    if translated := community['strings'].get('name'):
        return translated

    # finally use the English community name
    return community['strings']['community']


PREFIX = 'osm_community_index.communities.'
NPM_OCI_DIR = Path('node_modules/osm-community-index')

# load the OCI data from the npm package
resources = (NPM_OCI_DIR / 'dist/resources.min.json').read_bytes()

# copy the resources file to the config directory
Path('config/resources.json').write_bytes(resources)

communities = json.loads(resources)['resources']

# filter the communities here to avoid loading excessive numbers of translations
communities = tuple(c for c in communities.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')

for path in (NPM_OCI_DIR / 'i18n').glob('*.yaml'):
    locale = path.stem.replace('_', '-')

    with path.open('rb') as f:
        locale_data: dict = next(iter(yaml.safe_load(f).values()))

    data = {}

    for community in communities:
        community_id: str = community['id']
        strings = locale_data.get(community_id, {})
        strings['name'] = resolve_name(community, locale_data)

        if community_id in data:
            raise ValueError(f'Duplicate community ID {community_id!r}')

        data[community_id] = strings

    data = flatten(data)

    locale_dir = Path(f'config/locale/{locale}/LC_MESSAGES')
    locale_dir.mkdir(parents=True, exist_ok=True)

    with (locale_dir / 'oci.po').open('w') as f:
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write(f'"Language: {locale}\\n"\n')

        for k, v in data.items():
            k = PREFIX + k
            v = (
                v.replace('\\', '\\\\')  # escape backslashes
                .replace('"', '\\"')  # escape double quotes
                .replace('\n', '\\n')  # escape newlines
            )
            f.write('\n#: Generated from osm-community-index\n')
            f.write(f'msgctxt "{k}"\n')
            f.write(f'msgid "{k}"\n')
            f.write(f'msgstr "{v}"\n')
