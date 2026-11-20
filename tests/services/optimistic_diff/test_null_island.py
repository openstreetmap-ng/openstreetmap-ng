from copy import deepcopy

import pytest
from shapely import Point

from app.exceptions.api_error import APIError
from app.lib.auth.context import auth_context, auth_user
from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.services.optimistic_diff import OptimisticDiff
from speedup import typed_element_id


def _node(changeset_id, id, x=0, y=0, version=1) -> ElementInit:
    return {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(id)),
        'version': version,
        'visible': True,
        'tags': {},
        'point': Point(x, y),
        'members': None,
        'members_roles': None,
    }


async def test_reject_multiple_null_island_nodes(changeset_id: ChangesetId):
    with pytest.raises(APIError) as exc:
        await OptimisticDiff.run([
            _node(changeset_id, -1),
            _node(changeset_id, -2),
        ])
    assert exc.value.status_code == 400
    assert 'Null Island' in exc.value.detail


async def test_allow_single_null_island_node(changeset_id: ChangesetId):
    result = await OptimisticDiff.run([
        _node(changeset_id, -1),
        _node(changeset_id, -2, x=0.0000001),
    ])
    assert len(result) == 2


async def test_count_final_state_not_intermediate_versions(changeset_id: ChangesetId):
    result = await OptimisticDiff.run([
        _node(changeset_id, -1),
        _node(changeset_id, -2),
        _node(changeset_id, -2, x=1, version=2),
    ])
    assert len(result) == 2


@pytest.mark.parametrize('role', ['moderator', 'administrator'])
async def test_privileged_user_bypass(changeset_id: ChangesetId, role):
    user = deepcopy(auth_user())
    assert user is not None
    user['roles'] = [role]
    with auth_context(user):
        result = await OptimisticDiff.run([
            _node(changeset_id, -1),
            _node(changeset_id, -2),
        ])
    assert len(result) == 2
