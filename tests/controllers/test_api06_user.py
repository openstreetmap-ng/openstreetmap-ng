from httpx import AsyncClient

from app.config import APP_URL
from app.lib.locale import DEFAULT_LOCALE


async def test_current_user(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # get user details
    r = await client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    user: dict = r.json()['user']

    assert 'id' in user
    assert 'account_created' in user
    assert 'description' in user
    assert user['display_name'] == 'user1'
    assert user['contributor_terms']['agreed'] is True
    assert user['contributor_terms']['pd'] is False
    assert user['img']['href'].startswith(APP_URL)
    assert user['roles'] == []
    assert user['changesets']['count'] >= 0
    assert user['traces']['count'] >= 0
    assert user['blocks']['received']['count'] >= 0
    assert user['blocks']['received']['active'] >= 0
    assert user['blocks']['issued']['count'] >= 0
    assert user['blocks']['issued']['active'] >= 0
    assert user['languages'] == [DEFAULT_LOCALE]
    assert user['messages']['received']['count'] >= 0
    assert user['messages']['received']['unread'] >= 0
    assert user['messages']['sent']['count'] >= 0
