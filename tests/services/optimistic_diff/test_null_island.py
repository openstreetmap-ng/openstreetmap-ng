import pytest
from shapely import Point

from app.exceptions.api_error import APIError
from app.lib.auth.context import auth_context, auth_user
from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from speedup import typed_element_id


def _node(changeset_id: ChangesetId, id: int, point: Point) -> ElementInit:
    return {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(id)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': point,
        'members': None,
        'members_roles': None,
    }


async def test_reject_multiple_null_island_nodes_atomically(changeset_id: ChangesetId):
    nodes = [_node(changeset_id, id, Point(0, 0)) for id in (-1, -2)]
    with pytest.raises(APIError, match='multiple nodes at') as error:
        await OptimisticDiff.run(nodes)
    assert error.value.status_code == 400
    assert not await ElementQuery.find_by_changeset(changeset_id)


async def test_reject_null_island_across_uploads(changeset_id: ChangesetId):
    first = _node(changeset_id, -1, Point(0, 0))
    await OptimisticDiff.run([first])
    with pytest.raises(APIError, match='multiple nodes at'):
        await OptimisticDiff.run([_node(changeset_id, -1, Point(0, 0))])
    assert len(await ElementQuery.find_by_changeset(changeset_id)) == 1


async def test_multiple_revisions_of_one_null_island_node(changeset_id: ChangesetId):
    node = _node(changeset_id, -1, Point(0, 0))
    assigned = await OptimisticDiff.run([node, node | {'version': 2}])
    typed_id = assigned[node['typed_id']][0]
    await OptimisticDiff.run([node | {'typed_id': typed_id, 'version': 3}])
    current = await ElementQuery.find_by_refs([typed_id], limit=1)
    assert current[0]['version'] == 3


@pytest.mark.parametrize('delete', [False, True])
async def test_replace_previous_null_island_node(
    changeset_id: ChangesetId, delete: bool
):
    node = _node(changeset_id, -1, Point(0, 0))
    assigned = await OptimisticDiff.run([node])
    typed_id = assigned[node['typed_id']][0]
    repair = node | {
        'typed_id': typed_id,
        'version': 2,
        'visible': not delete,
        'point': None if delete else Point(1, 1),
        'tags': None if delete else {},
    }
    await OptimisticDiff.run([repair, _node(changeset_id, -1, Point(0, 0))])
    # A repaired historical revision must not count in subsequent uploads either.
    replacement = next(
        e
        for e in await ElementQuery.find_by_changeset(changeset_id)
        if e['typed_id'] != typed_id
    )
    await OptimisticDiff.run([replacement | {'version': 2}])


async def test_final_state_allows_intermediate_null_island(changeset_id: ChangesetId):
    nodes = [_node(changeset_id, id, Point(0, 0)) for id in (-1, -2)]
    result = await OptimisticDiff.run([
        *nodes,
        nodes[1] | {'version': 2, 'point': Point(1, 1)},
    ])
    assert len(result) == 2


async def test_reject_moving_two_nodes_to_null_island(changeset_id: ChangesetId):
    nodes = [_node(changeset_id, id, Point(1, 1)) for id in (-1, -2)]
    assigned = await OptimisticDiff.run(nodes)
    with pytest.raises(APIError, match='multiple nodes at'):
        await OptimisticDiff.run([
            node
            | {
                'typed_id': assigned[node['typed_id']][0],
                'version': 2,
                'point': Point(0, 0),
            }
            for node in nodes
        ])
    current = await ElementQuery.find_by_refs([value[0] for value in assigned.values()])
    assert all(e['version'] == 1 and e['point'] == Point(1, 1) for e in current)


@pytest.mark.parametrize('role', ['moderator', 'administrator'])
async def test_moderator_exception_and_cleanup(changeset_id: ChangesetId, role):
    nodes = [_node(changeset_id, id, Point(0, 0)) for id in (-1, -2)]
    with auth_context(auth_user(required=True) | {'roles': [role]}):
        assigned = await OptimisticDiff.run(nodes)
    # An ordinary user can repair the invalid state created by an exempt user.
    await OptimisticDiff.run([
        node
        | {
            'typed_id': assigned[node['typed_id']][0],
            'version': 2,
            'point': Point(1, 1),
        }
        for node in nodes
    ])


@pytest.mark.parametrize('point', [Point(0, 1), Point(1, 0), Point(0.0000001, 0)])
async def test_axis_and_nearby_nodes_allowed(changeset_id: ChangesetId, point: Point):
    result = await OptimisticDiff.run([
        _node(changeset_id, -1, Point(0, 0)),
        _node(changeset_id, -2, point),
    ])
    assert len(result) == 2
