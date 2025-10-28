import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from speedup.element_type import typed_element_id
from tests.utils.assert_model import assert_model


async def test_way_with_single_node_member(changeset_id: ChangesetId):
    # Arrange
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

    # Act
    assigned_ref_map = await OptimisticDiff.run([node, way])

    # Assert
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([node_typed_id], limit=1)
    assert_model(elements[0], node | {'typed_id': node_typed_id})
    elements = await ElementQuery.find_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0], way | {'typed_id': way_typed_id, 'members': [node_typed_id]}
    )


async def test_way_with_multiple_nodes(changeset_id: ChangesetId):
    # Arrange
    node1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'name': 'Node 1'},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-2)),
        'version': 1,
        'visible': True,
        'tags': {'name': 'Node 2'},
        'point': Point(1, 1),
        'members': None,
        'members_roles': None,
    }
    way: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'highway': 'residential'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('node', ElementId(-2)),
            typed_element_id('node', ElementId(-1)),
        ],
        'members_roles': None,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([node1, node2, way])

    # Assert
    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0],
        way
        | {
            'typed_id': way_typed_id,
            'members': [node1_typed_id, node2_typed_id, node1_typed_id],
        },
    )


async def test_relation_with_mixed_members(changeset_id: ChangesetId):
    # Arrange
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'name': 'Test Node'},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    way: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'highway': 'residential'},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    relation: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('way', ElementId(-1)),
        ],
        'members_roles': ['node_role', 'way_role'],
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([node, way, relation])

    # Assert
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([relation_typed_id], limit=1)
    assert_model(
        elements[0],
        relation
        | {'typed_id': relation_typed_id, 'members': [node_typed_id, way_typed_id]},
    )


async def test_relation_with_self_reference(changeset_id: ChangesetId):
    # Create self-referencing relation
    relation: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('relation', ElementId(-1))],
        'members_roles': ['role'],
    }
    relation_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }
    assigned_ref_map = await OptimisticDiff.run([relation, relation_delete])
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Verify both versions
    elements = await ElementQuery.find_by_versioned_refs([
        (relation_typed_id, 1),
        (relation_typed_id, 2),
    ])
    version_map = {e['version']: e for e in elements}
    assert_model(
        version_map[1],
        relation | {'typed_id': relation_typed_id, 'members': [relation_typed_id]},
    )
    assert_model(version_map[2], relation_delete | {'typed_id': relation_typed_id})


async def test_delete_way_then_referenced_node(changeset_id: ChangesetId):
    # Arrange
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
    way_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([node, way, way_delete, node_delete])

    # Assert
    node_versions = assigned_ref_map[typed_element_id('node', ElementId(-1))]
    assert len(node_versions) == 2
    node_typed_id = node_versions[0]
    way_versions = assigned_ref_map[typed_element_id('way', ElementId(-1))]
    assert len(way_versions) == 2
    way_typed_id = way_versions[0]
    nodes = await ElementQuery.find_by_refs([node_typed_id], limit=1)
    assert_model(nodes[0], node_delete | {'typed_id': node_typed_id})
    ways = await ElementQuery.find_by_refs([way_typed_id], limit=1)
    assert_model(ways[0], way_delete | {'typed_id': way_typed_id})


async def test_delete_fails_when_node_still_referenced_by_way(
    changeset_id: ChangesetId,
):
    """Test that deletion fails due to sequence ordering: node delete is checked before way delete is applied."""
    # Arrange
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
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }
    way_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, way, node_delete, way_delete])


async def test_create_fails_when_referencing_deleted_element(changeset_id: ChangesetId):
    # Arrange
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
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
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

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, node_delete, way])


async def test_create_fails_when_referencing_nonexistent_element(
    changeset_id: ChangesetId,
):
    # Arrange
    relation: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId((1 << 56) - 1))],
        'members_roles': [''],
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([relation])
