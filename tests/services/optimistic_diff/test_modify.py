import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from speedup.element_type import typed_element_id
from tests.utils.assert_model import assert_model


async def test_modify_node_tags_and_location(changeset_id: ChangesetId):
    # Arrange
    node_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'created': 'yes'},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'modified': 'yes'},
        'point': Point(1, 2),
        'members': None,
        'members_roles': None,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([node_create, node_modify])

    # Assert
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([node_typed_id], limit=1)
    assert_model(elements[0], node_modify | {'typed_id': node_typed_id})


async def test_modify_way_members(changeset_id: ChangesetId):
    # Create nodes
    node1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-2)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(1, 1),
        'members': None,
        'members_roles': None,
    }
    way_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'highway': 'residential'},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    way_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'highway': 'residential', 'modified': 'yes'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('node', ElementId(-2)),
        ],
        'members_roles': None,
    }
    assigned_ref_map = await OptimisticDiff.run([node1, node2, way_create, way_modify])

    # Verify modified way
    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0],
        way_modify
        | {'typed_id': way_typed_id, 'members': [node1_typed_id, node2_typed_id]},
    )


async def test_modify_relation_members_and_roles(changeset_id: ChangesetId):
    # Create base elements
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    way: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    relation_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': ['old_role'],
    }
    relation_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'type': 'test', 'modified': 'yes'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('way', ElementId(-1)),
        ],
        'members_roles': ['new_node_role', 'way_role'],
    }
    assigned_ref_map = await OptimisticDiff.run([
        node,
        way,
        relation_create,
        relation_modify,
    ])

    # Verify modified relation
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([relation_typed_id], limit=1)
    assert_model(
        elements[0],
        relation_modify
        | {'typed_id': relation_typed_id, 'members': [node_typed_id, way_typed_id]},
    )


async def test_modify_fails_with_version_gap(changeset_id: ChangesetId):
    # Arrange
    node_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 3,  # Should be 2
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([node_create, node_modify])


async def test_multiple_consecutive_modifications(changeset_id: ChangesetId):
    # Arrange
    nodes: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': i,
            'visible': True,
            'tags': {'version': str(i)},
            'point': Point(i, i),
            'members': None,
            'members_roles': None,
        }
        for i in range(1, 4)
    ]

    # Act
    assigned_ref_map = await OptimisticDiff.run(nodes)

    # Assert
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    elements = await ElementQuery.find_versions_by_ref(node_typed_id, sort_dir='asc')
    for element, node in zip(elements, nodes, strict=True):
        assert_model(element, node | {'typed_id': node_typed_id})


async def test_modify_relation_to_add_self_reference(changeset_id: ChangesetId):
    # Arrange
    relation_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [],
        'members_roles': [],
    }
    relation_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [typed_element_id('relation', ElementId(-1))],
        'members_roles': ['self'],
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([relation_create, relation_modify])

    # Assert
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([relation_typed_id], limit=1)
    assert_model(
        elements[0],
        relation_modify
        | {'typed_id': relation_typed_id, 'members': [relation_typed_id]},
    )


async def test_modify_relation_to_remove_self_reference(changeset_id: ChangesetId):
    # Arrange
    relation_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [typed_element_id('relation', ElementId(-1))],
        'members_roles': ['self'],
    }
    relation_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [],
        'members_roles': [],
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([relation_create, relation_modify])

    # Assert
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([relation_typed_id], limit=1)
    assert_model(elements[0], relation_modify | {'typed_id': relation_typed_id})


async def test_modify_way_add_then_remove_node_reference(changeset_id: ChangesetId):
    # Create nodes and way
    node1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-2)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(1, 1),
        'members': None,
        'members_roles': None,
    }
    way_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    way_add_node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('node', ElementId(-2)),
        ],
        'members_roles': None,
    }
    way_remove_node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 3,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    assigned_ref_map = await OptimisticDiff.run([
        node1,
        node2,
        way_create,
        way_add_node,
        way_remove_node,
    ])

    # Verify final state
    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0],
        way_remove_node | {'typed_id': way_typed_id, 'members': [node1_typed_id]},
    )


async def test_create_modify_delete_lifecycle_in_one_batch(
    changeset_id: ChangesetId,
):
    # Arrange
    node_v1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'created': 'yes'},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node_v2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'modified': 'yes'},
        'point': Point(1, 1),
        'members': None,
        'members_roles': None,
    }
    node_v3: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 3,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([node_v1, node_v2, node_v3])

    # Assert - all three versions should exist
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    elements = await ElementQuery.find_versions_by_ref(node_typed_id, sort_dir='asc')
    assert len(elements) == 3
    version_map = {e['version']: e for e in elements}
    assert_model(version_map[1], node_v1 | {'typed_id': node_typed_id})
    assert_model(version_map[2], node_v2 | {'typed_id': node_typed_id})
    assert_model(version_map[3], node_v3 | {'typed_id': node_typed_id})
