import pytest
from shapely import Point

from app.exceptions.api_error import APIError
from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.queries.changeset_query import ChangesetQuery
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


async def test_reject_null_island_batch_atomically(changeset_id: ChangesetId):
    sequence_id = await ElementQuery.get_current_sequence_id()
    with pytest.raises(APIError, match='multiple nodes at') as exc:
        await OptimisticDiff.run([
            _node(changeset_id, -1, Point(0, 0)),
            _node(changeset_id, -2, Point(0, 0)),
        ])
    assert exc.value.status_code == 412
    assert await ElementQuery.get_current_sequence_id() == sequence_id
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None and changeset['size'] == 0


async def test_reject_null_island_across_uploads(changeset_id: ChangesetId):
    await OptimisticDiff.run([_node(changeset_id, -1, Point(0, 0))])
    sequence_id = await ElementQuery.get_current_sequence_id()
    with pytest.raises(APIError, match='multiple nodes at'):
        await OptimisticDiff.run([_node(changeset_id, -1, Point(0, 0))])
    assert await ElementQuery.get_current_sequence_id() == sequence_id


async def test_modify_single_null_island_node(changeset_id: ChangesetId):
    node = _node(changeset_id, -1, Point(0, 0))
    result = await OptimisticDiff.run([node])
    tid = result[node['typed_id']][0]
    modified: ElementInit = node | {
        'typed_id': tid,
        'version': 2,
        'tags': {'name': 'Null Island'},
    }
    result = await OptimisticDiff.run([modified])
    assert result[tid] == (tid, [2])


@pytest.mark.parametrize('delete', [False, True])
async def test_remove_null_island_node_and_add_replacement(
    changeset_id: ChangesetId, delete: bool
):
    node = _node(changeset_id, -1, Point(0, 0))
    result = await OptimisticDiff.run([node])
    tid = result[node['typed_id']][0]
    removed: ElementInit = node | {
        'typed_id': tid,
        'version': 2,
        'visible': not delete,
        'point': None if delete else Point(1, 1),
    }
    result = await OptimisticDiff.run([removed, _node(changeset_id, -1, Point(0, 0))])
    assert len(result) == 2


async def test_reject_moving_multiple_nodes_to_null_island(changeset_id: ChangesetId):
    nodes = [_node(changeset_id, -1, Point(1, 1)), _node(changeset_id, -2, Point(2, 2))]
    result = await OptimisticDiff.run(nodes)
    moved: list[ElementInit] = [
        node
        | {'typed_id': result[node['typed_id']][0], 'version': 2, 'point': Point(0, 0)}
        for node in nodes
    ]
    with pytest.raises(APIError, match='multiple nodes at'):
        await OptimisticDiff.run(moved)
    stored = await ElementQuery.find_by_refs([node['typed_id'] for node in moved])
    assert all(node['version'] == 1 for node in stored)


async def test_only_final_revision_counts(changeset_id: ChangesetId):
    node = _node(changeset_id, -1, Point(0, 0))
    moved: ElementInit = node | {'version': 2, 'point': Point(1, 1)}
    result = await OptimisticDiff.run([
        node,
        moved,
        _node(changeset_id, -2, Point(0, 0)),
    ])
    assert len(result) == 2
