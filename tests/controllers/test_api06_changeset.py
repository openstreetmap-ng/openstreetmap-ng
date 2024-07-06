from httpx import AsyncClient

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.format import Format06
from app.lib.xmltodict import XMLToDict


async def test_changeset_crud(client: AsyncClient):
    assert LEGACY_HIGH_PRECISION_TIME
    client.headers['Authorization'] = 'User user1'

    # create changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'changeset': {
                        'tag': [
                            {'@k': 'comment', '@v': 'create'},
                            {'@k': 'created_by', '@v': test_changeset_crud.__name__},
                            {'@k': 'remove_me', '@v': 'remove_me'},
                        ]
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # read changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']
    tags = Format06.decode_tags_and_validate(changeset['tag'])

    assert changeset['@id'] == changeset_id
    assert changeset['@user'] == 'user1'
    assert changeset['@open'] is True
    assert changeset['@created_at'] == changeset['@updated_at']
    assert '@closed_at' not in changeset
    assert len(tags) == 3
    assert tags['comment'] == 'create'

    last_updated_at = changeset['@updated_at']

    # update changeset
    r = await client.put(
        f'/api/0.6/changeset/{changeset_id}',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'changeset': {
                        'tag': [
                            {'@k': 'comment', '@v': 'update'},
                            {'@k': 'created_by', '@v': test_changeset_crud.__name__},
                        ]
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']
    tags = Format06.decode_tags_and_validate(changeset['tag'])

    assert changeset['@updated_at'] > last_updated_at
    assert len(tags) == 2
    assert tags['comment'] == 'update'
    assert 'remove_me' not in tags

    last_updated_at = changeset['@updated_at']

    # close changeset
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text
    assert not r.content

    # read changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']

    assert changeset['@open'] is False
    assert changeset['@updated_at'] > last_updated_at
    assert '@closed_at' in changeset
    assert '@min_lat' not in changeset
    assert '@max_lat' not in changeset
    assert '@min_lon' not in changeset
    assert '@max_lon' not in changeset
    assert changeset['@changes_count'] == 0


async def test_changesets_unauthorized_get_request(client: AsyncClient):
    r = await client.get('/api/0.6/changesets')
    assert r.is_success, r.text

    changesets: dict = XMLToDict.parse(r.content)['osm']
    assert changesets['changeset'] is not None
