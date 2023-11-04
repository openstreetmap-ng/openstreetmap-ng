import os
from glob import glob
from os import path

import httpx
import yaml


def flatten(data: dict, parent_key='', separator='.') -> dict:
    items = {}
    for k, v in data.items():
        new_key = f'{parent_key}{separator}{k}' if parent_key else k
        if isinstance(v, dict):
            items.update(flatten(v, new_key, separator=separator))
        else:
            items[new_key] = v
    return items


def resolve_name(community: dict, community_locale: dict) -> str:
    # if theres an explicitly translated name then use that
    if translated := community_locale.get(community['id'], {}).get('name'):
        return translated

    # if not, then look up the default translated name for this type of community, and interpolate the template
    if (
        (template := community_locale.get('_defaults', {}).get(community['type'], {}).get('name')) and
        (community_name := community_locale.get('_communities', {}).get(community['strings'].get('communityID')))
    ):
        return template.format(community=community_name)

    # otherwise fall back to the English resource name
    if translated := community['strings'].get('name'):
        return translated

    # finally use the English community name
    return community['strings']['community']


PREFIX = 'osm_community_index.communities.'

# fetch resources from github because for some reason they are not included in the npm package
r = httpx.get('https://raw.githubusercontent.com/osmlab/osm-community-index/main/dist/resources.min.json')
r.raise_for_status()

with open('config/resources.json', 'wb') as f:
    f.write(r.read())

communities = r.json()['resources']

# filter the communities here to avoid loading excessive numbers of translations
communities = tuple(c for c in communities.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')

for f in glob('node_modules/osm-community-index/i18n/*.yaml'):
    locale = path.basename(f).replace('.yaml', '').replace('_', '-')

    with open(f) as f:
        community_locale = next(iter(yaml.safe_load(f).values()))

    data = {}

    for community in communities:
        id_ = community['id']
        strings = community_locale.get(id_, {})
        strings['name'] = resolve_name(community, community_locale)
        assert id_ not in data, f'Duplicate community ID {id_!r}'
        data[id_] = strings

    data = flatten(data)

    locale_dir = f'config/locale/{locale}/LC_MESSAGES'
    os.makedirs(locale_dir, exist_ok=True)

    with open(f'{locale_dir}/oci.po', 'w') as f:
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write(f'"Language: {locale}\\n"\n')

        for k, v in data.items():
            k = PREFIX + k
            v = (
                v
                .replace('\\', '\\\\')  # escape backslashes
                .replace('"', '\\"')  # escape double quotes
                .replace('\n', '\\n')  # escape newlines
            )
            f.write(f'\n#: Generated from osm-community-index\n')
            f.write(f'msgctxt "{k}"\n')
            f.write(f'msgid "{k}"\n')
            f.write(f'msgstr "{v}"\n')
