import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId, split_typed_element_id, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff


async def test_modify_node_tags_and_location(changeset_id: ChangesetId):
    # Create a node element
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

    # Modify the node's tags and location
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

    # Push elements to the database
    elements = [node_create, node_modify]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned ID
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Retrieve the node and check its properties
    nodes = await ElementQuery.get_by_refs([node_typed_id], limit=1)
    assert nodes, 'Node must exist in database'
    node_element = nodes[0]

    # Verify the node has been properly modified
    assert node_element['changeset_id'] == changeset_id, 'Node must have correct changeset ID'
    element_type, element_id = split_typed_element_id(node_typed_id)
    assert element_type == 'node', 'Element must be a node'
    assert element_id > 0, 'Element must have a positive ID'
    assert node_element['version'] == 2, 'Node must be at version 2'
    assert node_element['visible'] is True, 'Node must be visible'
    assert node_element['tags'] == {'modified': 'yes'}, 'Node must have updated tags'
    assert node_element['point'] == Point(1, 2), 'Node must have updated location'
    assert node_element['members'] is None, 'Node must have no members'


async def test_modify_way_members(changeset_id: ChangesetId):
    # Create two node elements
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

    # Create a way with one node
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

    # Modify the way to include both nodes
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

    # Push all elements to the database
    elements = [node1, node2, way_create, way_modify]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned IDs
    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Retrieve the way and check its properties
    ways = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert ways, 'Way must exist in database'
    way_element = ways[0]

    # Verify the way has been properly modified
    assert way_element['version'] == 2, 'Way must be at version 2'
    assert way_element['visible'] is True, 'Way must be visible'
    assert way_element['tags'] == {'highway': 'residential', 'modified': 'yes'}, 'Way must have updated tags'
    assert way_element['members'] is not None, 'Way must have members'
    assert len(way_element['members']) == 2, 'Way must have exactly two members'
    assert way_element['members'][0] == node1_typed_id, 'First way member must be Node 1'
    assert way_element['members'][1] == node2_typed_id, 'Second way member must be Node 2'


async def test_modify_relation_members_and_roles(changeset_id: ChangesetId):
    # Create a node and a way
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

    # Create a relation with just the node
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

    # Modify the relation to include both node and way with different roles
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

    # Push all elements to the database
    elements = [node, way, relation_create, relation_modify]
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned IDs
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Retrieve the relation and check its properties
    relations = await ElementQuery.get_by_refs([relation_typed_id], limit=1)
    assert relations, 'Relation must exist in database'
    relation_element = relations[0]

    # Verify the relation has been properly modified
    assert relation_element['version'] == 2, 'Relation must be at version 2'
    assert relation_element['visible'] is True, 'Relation must be visible'
    assert relation_element['tags'] == {'type': 'test', 'modified': 'yes'}, 'Relation must have updated tags'
    assert relation_element['members'] is not None, 'Relation must have members'
    assert len(relation_element['members']) == 2, 'Relation must have exactly two members'
    assert relation_element['members'][0] == node_typed_id, 'First relation member must be the node'
    assert relation_element['members'][1] == way_typed_id, 'Second relation member must be the way'
    assert relation_element['members_roles'][0] == 'new_node_role', 'Node member must have updated role'  # type: ignore
    assert relation_element['members_roles'][1] == 'way_role', 'Way member must have correct role'  # type: ignore


async def test_invalid_version_gap(changeset_id: ChangesetId):
    # Create a node element
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

    # Try to modify the node with a version gap (skipping version 2)
    node_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 3,  # Invalid: should be 2
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to version gap
    elements = [node_create, node_modify]
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_multiple_consecutive_modifications(changeset_id: ChangesetId):
    # Push elements to the database
    elements: list[ElementInit] = [
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
    assigned_ref_map = await OptimisticDiff.run(elements)

    # Get the assigned ID
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Retrieve all versions of the node
    node_versions = await ElementQuery.get_versions_by_ref(node_typed_id, sort='asc')
    assert len(node_versions) == 3, 'Node must have three versions'

    # Verify each version has the correct properties
    for i, node in enumerate(node_versions, 1):
        assert node['version'] == i, f'Node version {i} must have correct version number'
        assert node['tags'] == {'version': str(i)}, f'Node version {i} must have correct tags'
        assert node['point'] == Point(i, i), f'Node version {i} must have correct location'
