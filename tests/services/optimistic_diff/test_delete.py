import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from tests.utils.assert_model import assert_model


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
    assigned_ref_map = await OptimisticDiff.run([node, way, node_delete])
    typed_id_node = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Verify the created element
    elements = await ElementQuery.get_by_refs([typed_id_node], limit=1)
    assert_model(elements[0], node | {'typed_id': typed_id_node})


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
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, node_delete1, node_delete2])


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
    elements = await ElementQuery.get_by_refs([typed_id], limit=1)
    assert_model(elements[0], node | {'typed_id': typed_id})

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

    # Verify it was deleted
    elements = await ElementQuery.get_by_refs([typed_id], limit=1)
    assert_model(elements[0], node_delete)


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
    assigned_ref_map = await OptimisticDiff.run([node1, node2, way])
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

    # Verify it was deleted
    elements = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert_model(elements[0], way_delete)


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
