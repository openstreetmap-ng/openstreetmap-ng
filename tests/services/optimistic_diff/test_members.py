import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from tests.utils.assert_model import assert_model


async def test_way_with_single_node_member(changeset_id: ChangesetId):
    # Create a node element
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

    # Create a way that references the node
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

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([node, way])

    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Verify the created elements
    elements = await ElementQuery.get_by_refs([node_typed_id], limit=1)
    assert_model(elements[0], node | {'typed_id': node_typed_id})
    elements = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0],
        way
        | {
            'typed_id': way_typed_id,
            'members': [node_typed_id],
        },
    )


async def test_delete_way_then_referenced_node(changeset_id: ChangesetId):
    # Create a node element
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

    # Create a way that references the node
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

    # Delete the way first (this is necessary before deleting the node)
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

    # Then delete the node
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

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([node, way, way_delete, node_delete])

    node_versions = assigned_ref_map[typed_element_id('node', ElementId(-1))]
    assert len(node_versions) == 2
    node_typed_id = node_versions[0]
    way_versions = assigned_ref_map[typed_element_id('way', ElementId(-1))]
    assert len(way_versions) == 2
    way_typed_id = way_versions[0]

    # Verify both elements are now hidden
    nodes = await ElementQuery.get_by_refs([node_typed_id], limit=1)
    assert_model(nodes[0], node_delete | {'typed_id': node_typed_id})
    ways = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert_model(ways[0], way_delete | {'typed_id': way_typed_id})


async def test_relation_with_self_reference(changeset_id: ChangesetId):
    # Create a relation that references itself
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

    # Delete the relation
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

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([relation, relation_delete])

    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Verify the elements
    elements = await ElementQuery.get_by_versioned_refs([(relation_typed_id, 1), (relation_typed_id, 2)])
    version_map = {e['version']: e for e in elements}
    assert_model(
        version_map[1],
        relation
        | {
            'typed_id': relation_typed_id,
            'members': [relation_typed_id],
        },
    )
    assert_model(version_map[2], relation_delete | {'typed_id': relation_typed_id})


async def test_invalid_reference_to_nonexistent_node(changeset_id: ChangesetId):
    # Create a relation referencing a non-existent node
    relation: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId((1 << 56) - 1))],  # Non-existent node
        'members_roles': [''],
    }

    # Operation must fail due to reference to non-existent element
    with pytest.raises(Exception):
        await OptimisticDiff.run([relation])


async def test_invalid_reference_to_deleted_node(changeset_id: ChangesetId):
    # Create a node element
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

    # Delete the node
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

    # Create a way that references the deleted node
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

    # Operation must fail due to reference to deleted element
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, node_delete, way])


async def test_cannot_delete_node_referenced_by_way(changeset_id: ChangesetId):
    # Create a node element
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

    # Create a way that references the node
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

    # Try to delete the node while it's still referenced by the way
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

    # Also include way deletion, but node deletion comes first in the list
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

    # Operation must fail due to deleting a node that's still referenced
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, way, node_delete, way_delete])


async def test_way_with_multiple_nodes(changeset_id: ChangesetId):
    # Create two node elements
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

    # Create a way that references both nodes
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

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([node1, node2, way])

    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Verify the created element
    elements = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0],
        way
        | {
            'typed_id': way_typed_id,
            'members': [node1_typed_id, node2_typed_id, node1_typed_id],
        },
    )


async def test_relation_with_mixed_members(changeset_id: ChangesetId):
    # Create a node element
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

    # Create a way element
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

    # Create a relation that references both node and way
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

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([node, way, relation])

    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Verify the created element
    elements = await ElementQuery.get_by_refs([relation_typed_id], limit=1)
    assert_model(
        elements[0],
        relation
        | {
            'typed_id': relation_typed_id,
            'members': [node_typed_id, way_typed_id],
        },
    )
