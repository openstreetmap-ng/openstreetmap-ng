import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff


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
    elements = [node, way]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned IDs
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Retrieve the way and check its members
    ways = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert ways, 'Way must exist in database'
    way_element = ways[0]

    # Verify the way's member references the node
    assert way_element['members'] is not None, 'Way must have members'
    assert len(way_element['members']) == 1, 'Way must have exactly one member'
    assert way_element['members'][0] == node_typed_id, 'Way must reference the created node'

    # Verify the original node exists
    nodes = await ElementQuery.get_by_refs([node_typed_id], limit=1)
    assert nodes, 'Referenced node must exist in database'


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
    elements = [node, way, way_delete, node_delete]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Verify mapping contains expected elements with correct versions
    node_versions = assigned_ref_map[typed_element_id('node', ElementId(-1))]
    way_versions = assigned_ref_map[typed_element_id('way', ElementId(-1))]

    assert len(node_versions) == 2, 'Node must have two versions (create and delete)'
    assert len(way_versions) == 2, 'Way must have two versions (create and delete)'

    # Verify both elements are now hidden
    node_typed_id = node_versions[0]
    way_typed_id = way_versions[0]

    nodes = await ElementQuery.get_by_refs([node_typed_id], limit=1)
    ways = await ElementQuery.get_by_refs([way_typed_id], limit=1)

    assert len(nodes) == 1, 'Node must still exist in the database'
    assert not nodes[0]['visible'], 'Node must be hidden after deletion'
    assert len(ways) == 1, 'Way must still exist in the database'
    assert not ways[0]['visible'], 'Way must be hidden after deletion'


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
    elements = [relation, relation_delete]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned ID
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Retrieve the relation and check its members
    relations = await ElementQuery.get_by_refs([relation_typed_id], limit=1)
    assert relations, 'Relation must exist in database'
    relation_element = relations[0]

    # For a self-referential relation, the first version should have the relation itself as a member
    assert relation_element['members'] is not None, 'Relation must have members'
    assert len(relation_element['members']) == 1, 'Relation must have exactly one member'
    assert relation_element['members'][0] == relation_typed_id, 'Relation must reference itself'
    assert relation_element['members_roles'][0] == 'role', 'Relation member must have correct role'  # type: ignore

    # The second (deleted) version should have no members
    deleted_relations = await ElementQuery.get_by_refs([relation_typed_id], limit=2)
    deleted_relation = next(r for r in deleted_relations if r['version'] == 2)
    assert deleted_relation['members'] is None, 'Deleted relation must have no members'
    assert deleted_relation['members_roles'] is None, 'Deleted relation must have no members roles'


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
    elements = [node, node_delete, way]
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


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
    elements = [node, way, node_delete, way_delete]
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


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
        ],
        'members_roles': None,
    }

    # Push all elements to the database
    elements = [node1, node2, way]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned IDs
    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Retrieve the way and check its members
    ways = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert ways, 'Way must exist in database'
    way_element = ways[0]

    # Verify the way's members reference both nodes in the correct order
    assert way_element['members'] is not None, 'Way must have members'
    assert len(way_element['members']) == 2, 'Way must have exactly two members'
    assert way_element['members'][0] == node1_typed_id, 'First way member must be Node 1'
    assert way_element['members'][1] == node2_typed_id, 'Second way member must be Node 2'


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
    elements = [node, way, relation]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned IDs
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Retrieve the relation and check its members
    relations = await ElementQuery.get_by_refs([relation_typed_id], limit=1)
    assert relations, 'Relation must exist in database'
    relation_element = relations[0]

    # Verify the relation's members reference both the node and way with correct roles
    assert relation_element['members'] is not None, 'Relation must have members'
    assert len(relation_element['members']) == 2, 'Relation must have exactly two members'
    assert relation_element['members'][0] == node_typed_id, 'First relation member must be the node'
    assert relation_element['members'][1] == way_typed_id, 'Second relation member must be the way'
    assert relation_element['members_roles'][0] == 'node_role', 'Node member must have correct role'  # type: ignore
    assert relation_element['members_roles'][1] == 'way_role', 'Way member must have correct role'  # type: ignore
