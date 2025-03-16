import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff


async def test_delete_if_unused(changeset_id: ChangesetId):
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

    # Attempt to delete the node (mark it invisible)
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
        'delete_if_unused': True,
    }

    # Apply all changes
    elements = [node, way, node_delete]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Verify mapping exists for created elements
    typed_id_node = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Retrieve and check the node (should still be visible at version 1 since it's in use)
    nodes = await ElementQuery.get_by_refs([typed_id_node], limit=1)
    assert nodes, 'Node must exist in database'
    node_element = nodes[0]

    # Since the node is used by a way, "delete_if_unused" should have no effect
    # and the node should remain at version 1 and visible
    assert node_element['version'] == 1, 'Node must remain at version 1 when referenced by way'
    assert node_element['visible'] is True, 'Node must remain visible when referenced by way'


async def test_delete_invalid_repeated(changeset_id: ChangesetId):
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

    # Delete the node (mark it invisible) - first attempt
    node_delete1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Try to delete the node again - second attempt (should fail)
    node_delete2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 3,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to multiple delete operations on the same element
    elements = [node, node_delete1, node_delete2]
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_delete_node(changeset_id: ChangesetId):
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

    # Push the node to the database
    assigned_ref_map = await OptimisticDiff.run([node])
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Verify it was created
    nodes = await ElementQuery.get_by_refs([typed_id], limit=1)
    assert nodes, 'Node must exist in database'
    assert nodes[0]['visible'] is True, 'Node must be visible initially'

    # Delete the node (mark it invisible)
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_id,
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Apply the delete operation
    await OptimisticDiff.run([node_delete])

    # Retrieve the node and check that it's now hidden
    nodes = await ElementQuery.get_by_refs([typed_id], limit=1)
    assert nodes, 'Node must still exist in database after deletion'
    assert nodes[0]['visible'] is False, 'Node must be hidden after deletion'
    assert nodes[0]['version'] == 2, 'Node must be at version 2 after deletion'
    assert nodes[0]['tags'] is None, 'Deleted node must have no tags'
    assert nodes[0]['point'] is None, 'Deleted node must have no geometry'


async def test_delete_way_with_nodes(changeset_id: ChangesetId):
    # Create node elements
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

    # Create a way that references the nodes
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
        ],
        'members_roles': None,
    }

    # Push all elements to the database
    elements = [node1, node2, way]
    assigned_ref_map = await OptimisticDiff.run(elements)
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Delete the way (mark it invisible)
    way_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': way_typed_id,
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Apply the delete operation
    await OptimisticDiff.run([way_delete])

    # Retrieve the way and check that it's now hidden
    ways = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert ways, 'Way must still exist in database after deletion'
    assert ways[0]['visible'] is False, 'Way must be hidden after deletion'
    assert ways[0]['members'] is None, 'Deleted way must have no members'
    assert ways[0]['tags'] is None, 'Deleted way must have no tags'


async def test_delete_nonexistent_element(changeset_id: ChangesetId):
    # Try to delete a node that doesn't exist
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId((1 << 56) - 1)),  # Non-existent node
        'version': 2,  # Version must be > 1 for deletion
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to non-existent element
    with pytest.raises(Exception):
        await OptimisticDiff.run([node_delete])


async def test_delete_wrong_version(changeset_id: ChangesetId):
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

    # Push the node to the database
    assigned_ref_map = await OptimisticDiff.run([node])
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Try to delete the node with incorrect version (3 instead of 2)
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_id,
        'version': 3,  # Incorrect version (should be 2)
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to incorrect version
    with pytest.raises(Exception):
        await OptimisticDiff.run([node_delete])
