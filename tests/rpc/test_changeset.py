import pytest
from httpx import AsyncClient
from polyline_rs import encode_lonlat
from shapely import Point

from app.lib.io.xml_codec import XMLToDict
from app.models.db.element import ElementInit
from app.models.element import ElementId, TypedElementId
from app.models.proto.changeset_pb2 import GetDiffRequest, GetDiffResponse
from app.models.types import ChangesetId, SequenceId
from app.queries.element_query import ElementQuery
from app.rpc import changeset as changeset_rpc
from app.services.optimistic_diff import OptimisticDiff
from speedup import element_id, typed_element_id


async def _create_changeset(client: AsyncClient) -> ChangesetId:
    client.headers['Authorization'] = 'User user1'
    response = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': 'tests'}]}}
        }),
    )
    assert response.is_success, response.text
    return ChangesetId(int(response.text))


async def _get_diff(client: AsyncClient, changeset_id: ChangesetId):
    response = await client.post(
        '/rpc/changeset.Service/GetDiff',
        headers={'Content-Type': 'application/proto'},
        content=GetDiffRequest(id=changeset_id).SerializeToString(),
    )
    assert response.is_success, response.text
    return GetDiffResponse.FromString(response.content)


def _node(
    changeset_id: ChangesetId,
    typed_id: TypedElementId,
    version: int,
    point: Point | None,
) -> ElementInit:
    return {
        'changeset_id': changeset_id,
        'typed_id': typed_id,
        'version': version,
        'visible': point is not None,
        'tags': {},
        'point': point,
        'members': None,
        'members_roles': None,
    }


async def test_get_diff_collapses_multiple_versions(
    client: AsyncClient, changeset_id: ChangesetId
):
    node_ref = typed_element_id('node', ElementId(-1))
    nodes: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': node_ref,
            'version': version,
            'visible': True,
            'tags': {},
            'point': Point(version, version),
            'members': None,
            'members_roles': None,
        }
        for version in range(1, 4)
    ]
    assigned_ref_map = await OptimisticDiff.run(nodes)
    node_id = assigned_ref_map[node_ref][0]

    diff = await _get_diff(client, changeset_id)

    assert diff.num_elements == 1
    assert diff.num_truncated == 0
    assert not diff.context_truncated
    assert not diff.before.nodes
    assert not diff.before.ways
    assert not diff.after.ways
    assert len(diff.after.nodes) == 1
    assert diff.after.nodes[0].id == node_id
    assert diff.after.nodes[0].location.lon == 3
    assert diff.after.nodes[0].location.lat == 3


async def test_get_diff_uses_changeset_snapshot_for_way_members(
    client: AsyncClient, changeset_id: ChangesetId
):
    node1_ref = typed_element_id('node', ElementId(-1))
    node2_ref = typed_element_id('node', ElementId(-2))
    way_ref = typed_element_id('way', ElementId(-1))
    base_elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': node1_ref,
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(0, 0),
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': node2_ref,
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(1, 0),
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': way_ref,
            'version': 1,
            'visible': True,
            'tags': {'highway': 'residential'},
            'point': None,
            'members': [node1_ref, node2_ref],
            'members_roles': None,
        },
    ]
    assigned_ref_map = await OptimisticDiff.run(base_elements)
    node1_id = assigned_ref_map[node1_ref][0]
    node2_id = assigned_ref_map[node2_ref][0]
    way_id = assigned_ref_map[way_ref][0]

    move_changeset_id = await _create_changeset(client)
    await OptimisticDiff.run([
        {
            'changeset_id': move_changeset_id,
            'typed_id': node2_id,
            'version': 2,
            'visible': True,
            'tags': {},
            'point': Point(2, 0),
            'members': None,
            'members_roles': None,
        }
    ])

    target_changeset_id = await _create_changeset(client)
    await OptimisticDiff.run([
        {
            'changeset_id': target_changeset_id,
            'typed_id': way_id,
            'version': 2,
            'visible': True,
            'tags': {'highway': 'residential', 'surface': 'paved'},
            'point': None,
            'members': [node1_id, node2_id],
            'members_roles': None,
        }
    ])

    diff = await _get_diff(client, target_changeset_id)

    expected_line = encode_lonlat([[0, 0], [2, 0]], 6)
    assert diff.num_elements == 1
    assert [way.id for way in diff.before.ways] == [element_id(way_id)]
    assert [way.id for way in diff.after.ways] == [element_id(way_id)]
    assert diff.before.ways[0].line == expected_line
    assert diff.after.ways[0].line == expected_line


async def test_get_diff_create_then_delete_is_net_empty(
    client: AsyncClient, changeset_id: ChangesetId
):
    node_ref = typed_element_id('node', ElementId(-1))
    assigned_ref_map = await OptimisticDiff.run([
        {
            'changeset_id': changeset_id,
            'typed_id': node_ref,
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(1, 2),
            'members': None,
            'members_roles': None,
        }
    ])
    node_id = assigned_ref_map[node_ref][0]
    await OptimisticDiff.run([
        {
            'changeset_id': changeset_id,
            'typed_id': node_id,
            'version': 2,
            'visible': False,
            'tags': None,
            'point': None,
            'members': None,
            'members_roles': None,
        }
    ])

    diff = await _get_diff(client, changeset_id)

    assert diff.num_elements == 1
    assert not diff.before.nodes
    assert not diff.before.ways
    assert not diff.after.nodes
    assert not diff.after.ways


async def test_get_diff_excludes_interleaved_root_versions(
    client: AsyncClient, changeset_id: ChangesetId
):
    node_ref = typed_element_id('node', ElementId(-1))
    assigned = await OptimisticDiff.run([_node(changeset_id, node_ref, 1, Point(0, 0))])
    node_id = assigned[node_ref][0]

    target_id = await _create_changeset(client)
    assigned = await OptimisticDiff.run([_node(target_id, node_ref, 1, Point(10, 0))])
    marker_id = assigned[node_ref][0]

    other_id = await _create_changeset(client)
    await OptimisticDiff.run([_node(other_id, node_id, 2, Point(1, 0))])
    await OptimisticDiff.run([_node(target_id, node_id, 3, Point(2, 0))])
    await OptimisticDiff.run([_node(other_id, node_id, 4, Point(3, 0))])
    await OptimisticDiff.run([_node(target_id, marker_id, 2, Point(11, 0))])

    diff = await _get_diff(client, target_id)
    before = {node.id: node.location.lon for node in diff.before.nodes}
    after = {node.id: node.location.lon for node in diff.after.nodes}

    assert diff.num_elements == 2
    # The previous root version is the edit immediately before this changeset's
    # own first edit, not the version before its first unrelated upload.
    assert before == {element_id(node_id): 1}
    # A later upload in another changeset must not replace our final version.
    assert after == {element_id(node_id): 2, element_id(marker_id): 11}


async def test_get_diff_deleted_existing_node(
    client: AsyncClient, changeset_id: ChangesetId
):
    node_ref = typed_element_id('node', ElementId(-1))
    assigned = await OptimisticDiff.run([_node(changeset_id, node_ref, 1, Point(3, 4))])
    node_id = assigned[node_ref][0]
    target_id = await _create_changeset(client)
    await OptimisticDiff.run([_node(target_id, node_id, 2, None)])

    diff = await _get_diff(client, target_id)

    assert diff.num_elements == 1
    assert len(diff.before.nodes) == 1
    assert diff.before.nodes[0].id == element_id(node_id)
    assert diff.before.nodes[0].location.lon == 3
    assert diff.before.nodes[0].location.lat == 4
    assert not diff.before.ways
    assert not diff.after.nodes
    assert not diff.after.ways


async def test_get_diff_limits_distinct_roots(
    client: AsyncClient, changeset_id: ChangesetId, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(changeset_rpc, '_CHANGESET_DIFF_ELEMENTS_LIMIT', 2)
    first_ref = typed_element_id('node', ElementId(-1))
    second_ref = typed_element_id('node', ElementId(-2))
    third_ref = typed_element_id('node', ElementId(-3))
    assigned = await OptimisticDiff.run([
        *[
            _node(changeset_id, first_ref, version, Point(version, 0))
            for version in range(1, 4)
        ],
        _node(changeset_id, second_ref, 1, Point(4, 0)),
        _node(changeset_id, third_ref, 1, Point(5, 0)),
    ])

    refs = await ElementQuery.find_changeset_diff_refs(changeset_id, limit=2)
    all_versions = await ElementQuery.find_by_changeset(
        changeset_id, sort_by='sequence_id'
    )
    assert len(refs) == 2
    for typed_id, _, _, first_sequence, last_sequence, total in refs:
        versions = [e for e in all_versions if e['typed_id'] == typed_id]
        assert first_sequence == versions[0]['sequence_id']
        assert last_sequence == versions[-1]['sequence_id']
        assert total == 3

    diff = await _get_diff(client, changeset_id)

    assert diff.num_elements == 2
    assert diff.num_truncated == 1
    assert not diff.context_truncated
    assert not diff.before.nodes
    assert {node.id: node.location.lon for node in diff.after.nodes} == {
        element_id(assigned[first_ref][0]): 3,
        element_id(assigned[second_ref][0]): 4,
    }


async def test_get_diff_late_way_uses_its_own_context_cutoffs(
    client: AsyncClient, changeset_id: ChangesetId
):
    node1_ref = typed_element_id('node', ElementId(-1))
    node2_ref = typed_element_id('node', ElementId(-2))
    way_ref = typed_element_id('way', ElementId(-1))
    assigned = await OptimisticDiff.run([
        _node(changeset_id, node1_ref, 1, Point(10, 0))
    ])
    marker_id = assigned[node1_ref][0]

    other_id = await _create_changeset(client)
    assigned = await OptimisticDiff.run([
        _node(other_id, node1_ref, 1, Point(0, 0)),
        _node(other_id, node2_ref, 1, Point(1, 0)),
        {
            'changeset_id': other_id,
            'typed_id': way_ref,
            'version': 1,
            'visible': True,
            'tags': {'highway': 'residential'},
            'point': None,
            'members': [node1_ref, node2_ref],
            'members_roles': None,
        },
    ])
    node1_id = assigned[node1_ref][0]
    node2_id = assigned[node2_ref][0]
    way_id = assigned[way_ref][0]

    await OptimisticDiff.run([
        {
            'changeset_id': changeset_id,
            'typed_id': way_id,
            'version': 2,
            'visible': True,
            'tags': {'highway': 'residential', 'surface': 'paved'},
            'point': None,
            'members': [node1_id, node2_id],
            'members_roles': None,
        }
    ])
    await OptimisticDiff.run([_node(other_id, node2_id, 2, Point(2, 0))])
    await OptimisticDiff.run([_node(changeset_id, marker_id, 2, Point(11, 0))])

    diff = await _get_diff(client, changeset_id)

    expected_line = encode_lonlat([[0, 0], [1, 0]], 6)
    assert diff.num_elements == 2
    assert len(diff.before.ways) == len(diff.after.ways) == 1
    assert diff.before.ways[0].id == diff.after.ways[0].id == element_id(way_id)
    assert diff.before.ways[0].line == diff.after.ways[0].line == expected_line
    assert not diff.context_truncated


async def test_get_diff_keeps_shared_members_at_independent_cutoffs(
    client: AsyncClient, changeset_id: ChangesetId
):
    node1_ref = typed_element_id('node', ElementId(-1))
    node2_ref = typed_element_id('node', ElementId(-2))
    way_refs = [typed_element_id('way', ElementId(-id)) for id in (1, 2)]
    base: list[ElementInit] = [
        _node(changeset_id, node1_ref, 1, Point(0, 0)),
        _node(changeset_id, node2_ref, 1, Point(1, 0)),
    ]
    base.extend(
        {
            'changeset_id': changeset_id,
            'typed_id': way_ref,
            'version': 1,
            'visible': True,
            'tags': {'highway': 'residential'},
            'point': None,
            'members': [node1_ref, node2_ref],
            'members_roles': None,
        }
        for way_ref in way_refs
    )
    assigned = await OptimisticDiff.run(base)
    node1_id = assigned[node1_ref][0]
    node2_id = assigned[node2_ref][0]
    way_ids = [assigned[ref][0] for ref in way_refs]
    target_id = await _create_changeset(client)
    other_id = await _create_changeset(client)

    for index, way_id in enumerate(way_ids):
        if index:
            await OptimisticDiff.run([_node(other_id, node2_id, 2, Point(2, 0))])
        await OptimisticDiff.run([
            {
                'changeset_id': target_id,
                'typed_id': way_id,
                'version': 2,
                'visible': True,
                'tags': {'highway': 'residential', 'surface': 'paved'},
                'point': None,
                'members': [node1_id, node2_id],
                'members_roles': None,
            }
        ])

    diff = await _get_diff(client, target_id)

    expected = {
        element_id(way_ids[0]): encode_lonlat([[0, 0], [1, 0]], 6),
        element_id(way_ids[1]): encode_lonlat([[0, 0], [2, 0]], 6),
    }
    assert diff.num_elements == 2
    assert {way.id: way.line for way in diff.before.ways} == expected
    assert {way.id: way.line for way in diff.after.ways} == expected


async def test_get_diff_created_root_stays_absent_from_before_context(
    client: AsyncClient, changeset_id: ChangesetId
):
    node_ref = typed_element_id('node', ElementId(-1))
    relation_ref = typed_element_id('relation', ElementId(-1))
    assigned = await OptimisticDiff.run([_node(changeset_id, node_ref, 1, Point(5, 0))])
    node_id = assigned[node_ref][0]
    other_id = await _create_changeset(client)
    assigned = await OptimisticDiff.run([
        {
            'changeset_id': other_id,
            'typed_id': relation_ref,
            'version': 1,
            'visible': True,
            'tags': {'type': 'collection'},
            'point': None,
            'members': [node_id],
            'members_roles': ['part'],
        }
    ])
    await OptimisticDiff.run([
        {
            'changeset_id': changeset_id,
            'typed_id': assigned[relation_ref][0],
            'version': 2,
            'visible': True,
            'tags': {'type': 'collection', 'name': 'Updated'},
            'point': None,
            'members': [node_id],
            'members_roles': ['part'],
        }
    ])

    diff = await _get_diff(client, changeset_id)

    assert diff.num_elements == 2
    assert not diff.before.nodes
    assert not diff.before.ways
    assert len(diff.after.nodes) == 1
    assert diff.after.nodes[0].id == element_id(node_id)


async def test_get_diff_context_budget_is_shared_and_batched(
    client: AsyncClient, changeset_id: ChangesetId, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(changeset_rpc, '_CHANGESET_DIFF_CONTEXT_LIMIT', 3)
    node1_ref = typed_element_id('node', ElementId(-1))
    node2_ref = typed_element_id('node', ElementId(-2))
    way_refs = [typed_element_id('way', ElementId(-id)) for id in (1, 2)]
    relation_ref = typed_element_id('relation', ElementId(-1))
    base: list[ElementInit] = [
        _node(changeset_id, node1_ref, 1, Point(0, 0)),
        _node(changeset_id, node2_ref, 1, Point(1, 0)),
    ]
    base.extend(
        {
            'changeset_id': changeset_id,
            'typed_id': way_ref,
            'version': 1,
            'visible': True,
            'tags': {'highway': 'residential'},
            'point': None,
            'members': [node1_ref, node2_ref],
            'members_roles': None,
        }
        for way_ref in way_refs
    )
    base.append({
        'changeset_id': changeset_id,
        'typed_id': relation_ref,
        'version': 1,
        'visible': True,
        'tags': {'type': 'collection'},
        'point': None,
        'members': way_refs,
        'members_roles': ['part', 'part'],
    })
    assigned = await OptimisticDiff.run(base)
    target_id = await _create_changeset(client)
    await OptimisticDiff.run([
        {
            'changeset_id': target_id,
            'typed_id': assigned[relation_ref][0],
            'version': 2,
            'visible': True,
            'tags': {'type': 'collection', 'name': 'Updated'},
            'point': None,
            'members': [assigned[ref][0] for ref in way_refs],
            'members_roles': ['part', 'part'],
        }
    ])

    calls: list[int] = []
    find_by_snapshot_refs = ElementQuery.find_by_snapshot_refs

    async def traced(refs: list[tuple[TypedElementId, SequenceId]]):
        calls.append(len(refs))
        return await find_by_snapshot_refs(refs)

    monkeypatch.setattr(ElementQuery, 'find_by_snapshot_refs', traced)
    diff = await _get_diff(client, target_id)

    assert diff.num_elements == 1
    assert diff.context_truncated
    # Each side fetches two direct ways, then one member node. The second query
    # shares the first query's budget, rather than restarting it for every way.
    assert sorted(calls) == [1, 1, 2, 2]


@pytest.mark.parametrize('way_edit', ['first', 'last', 'create', 'delete'])
async def test_get_diff_direct_way_keeps_its_boundary_in_relation_context(
    client: AsyncClient, changeset_id: ChangesetId, way_edit: str
):
    node1_ref = typed_element_id('node', ElementId(-1))
    node2_ref = typed_element_id('node', ElementId(-2))
    way_ref = typed_element_id('way', ElementId(-1))
    relation_ref = typed_element_id('relation', ElementId(-1))
    assigned = await OptimisticDiff.run([
        _node(changeset_id, node1_ref, 1, Point(0, 0)),
        _node(changeset_id, node2_ref, 1, Point(1, 0)),
    ])
    node1_id = assigned[node1_ref][0]
    node2_id = assigned[node2_ref][0]
    target_id = await _create_changeset(client)
    other_id = await _create_changeset(client)

    def way(
        changeset: ChangesetId,
        typed_id: TypedElementId,
        version: int,
        *,
        visible: bool = True,
    ) -> ElementInit:
        return {
            'changeset_id': changeset,
            'typed_id': typed_id,
            'version': version,
            'visible': visible,
            'tags': {'highway': 'residential'} if visible else None,
            'point': None,
            'members': [node1_id, node2_id] if visible else None,
            'members_roles': None,
        }

    assigned = await OptimisticDiff.run([
        way(target_id if way_edit == 'create' else changeset_id, way_ref, 1)
    ])
    way_id = assigned[way_ref][0]

    def relation(
        changeset: ChangesetId,
        typed_id: TypedElementId,
        version: int,
        *,
        contains_way: bool = True,
    ) -> ElementInit:
        return {
            'changeset_id': changeset,
            'typed_id': typed_id,
            'version': version,
            'visible': True,
            'tags': {'type': 'collection', 'name': f'Version {version}'},
            'point': None,
            'members': [way_id] if contains_way else [],
            'members_roles': ['part'] if contains_way else [],
        }

    assigned = await OptimisticDiff.run([
        relation(other_id if way_edit == 'create' else changeset_id, relation_ref, 1)
    ])
    relation_id = assigned[relation_ref][0]

    if way_edit == 'first':
        await OptimisticDiff.run([way(target_id, way_id, 2)])
    elif way_edit in {'last', 'delete'}:
        await OptimisticDiff.run([
            relation(target_id, relation_id, 2, contains_way=way_edit != 'delete')
        ])

    # This move belongs to another changeset. Rendering the directly edited way
    # again at the relation's cutoff must not add a second historical geometry.
    await OptimisticDiff.run([_node(other_id, node2_id, 2, Point(2, 0))])

    if way_edit in {'first', 'create'}:
        await OptimisticDiff.run([relation(target_id, relation_id, 2)])
    else:
        await OptimisticDiff.run([
            way(target_id, way_id, 2, visible=way_edit != 'delete')
        ])

    diff = await _get_diff(client, target_id)
    assert diff.num_elements == 2
    assert not diff.num_truncated
    assert not diff.context_truncated
    expected_line = encode_lonlat(
        [[0, 0], [1 if way_edit in {'first', 'create'} else 2, 0]], 6
    )
    expected_way = [(element_id(way_id), expected_line)]
    # Assert the complete list, since converting to a dict would hide duplicates.
    assert [(way.id, way.line) for way in diff.before.ways] == (
        [] if way_edit == 'create' else expected_way
    )
    assert [(way.id, way.line) for way in diff.after.ways] == (
        [] if way_edit == 'delete' else expected_way
    )
