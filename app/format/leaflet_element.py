import logging
from collections.abc import Iterable, Sequence

import cython
import numpy as np
from polyline_rs import encode_lonlat
from shapely import Point, lib

from app.lib.query_features import QueryFeatureResult
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element import ElementId, ElementType
from app.models.proto.shared_pb2 import RenderNode, RenderObjectsData, RenderWay, SharedLonLat


class LeafletElementMixin:
    @staticmethod
    def encode_elements(
        elements: Iterable[Element],
        *,
        detailed: cython.char,
        areas: cython.char = True,
    ) -> RenderObjectsData:
        """
        Format elements into a minimal structure, suitable for map rendering.
        """
        node_id_map: dict[ElementId, Element] = {}
        ways: list[Element] = []
        member_nodes_ids: set[ElementId] = set()
        for element in elements:
            if element.type == 'node':
                node_id_map[element.id] = element
            elif element.type == 'way':
                ways.append(element)

        render_ways: list[RenderWay] = []
        for way in ways:
            way_members = way.members
            if way_members is None:
                raise AssertionError('Way members must be set')

            way_id = way.id
            member_nodes_ids.update(member.id for member in way_members)
            current_segment: list[Point] = []
            segments: list[list[Point]] = [current_segment]

            for node_ref in way_members:
                node = node_id_map.get(node_ref.id)
                if node is None:
                    # split way on gap
                    if current_segment:
                        current_segment = []
                        segments.append(current_segment)
                    continue

                point = node.point
                if point is None:
                    logging.warning(
                        'Missing point for node %d version %d (part of way %d version %d)',
                        node.id,
                        node.version,
                        way_id,
                        way.version,
                    )
                    continue

                current_segment.append(point)

            is_area = _check_way_area(way.tags, way_members) if areas and len(segments) == 1 else False
            for segment in segments:
                if not segment:
                    continue
                geom = lib.get_coordinates(np.asarray(segment, dtype=object), False, False).tolist()
                line = encode_lonlat(geom, 6)
                render_ways.append(RenderWay(id=way_id, line=line, area=is_area))

        encode_nodes = tuple(
            node
            for node in node_id_map.values()
            if _check_node_interesting(node, member_nodes_ids, detailed=detailed)  #
            and node.point is not None
        )
        encode_points = tuple(node.point for node in encode_nodes)
        geoms = lib.get_coordinates(np.asarray(encode_points, dtype=object), False, False).tolist()
        render_nodes = tuple(
            RenderNode(id=node.id, point=SharedLonLat(lon=geom[0], lat=geom[1]))
            for node, geom in zip(encode_nodes, geoms, strict=True)
        )
        return RenderObjectsData(
            nodes=render_nodes,
            ways=render_ways,
        )

    @staticmethod
    def encode_query_features(results: Iterable[QueryFeatureResult]) -> list[RenderObjectsData]:
        """
        Format query features results into a minimal structure, suitable for map rendering.
        """
        encoded: list[RenderObjectsData] = []
        for result in results:
            element = result.element
            element_type = element.type
            if element_type == 'node':
                point: Point = element.point  # pyright: ignore[reportAssignmentType]
                render_node = RenderNode(id=element.id, point=SharedLonLat(lon=point.x, lat=point.y))
                encoded.append(RenderObjectsData(nodes=(render_node,)))
            elif element_type == 'way':
                coords: Sequence[tuple[float, float]] = result.geoms[0]  # pyright: ignore[reportAssignmentType]
                render_way = RenderWay(id=element.id, line=encode_lonlat(coords, 6))
                encoded.append(RenderObjectsData(ways=(render_way,)))
            elif element_type == 'relation':
                nodes: list[RenderNode] = []
                ways: list[RenderWay] = []
                for geom in result.geoms:
                    if isinstance(geom, Point):
                        nodes.append(RenderNode(id=element.id, point=SharedLonLat(lon=geom.x, lat=geom.y)))
                    else:
                        coords: Sequence[tuple[float, float]] = geom
                        ways.append(RenderWay(id=element.id, line=encode_lonlat(coords, 6)))
                encoded.append(RenderObjectsData(nodes=tuple(nodes), ways=tuple(ways)))
            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')
        return encoded

    @staticmethod
    def group_related_elements(elements: Iterable[Element]) -> list[Sequence[Element]]:
        """
        Group elements that are related to each other.

        The primary element is the first element in the group.

        The same element can be present in multiple groups.
        """
        type_ids_map: dict[tuple[ElementType, ElementId], Element] = {}
        parents: list[Element] = []
        nodes: list[Element] = []
        member_nodes_ids: set[ElementId] = set()
        for element in elements:
            type_ids_map[(element.type, element.id)] = element
            if element.type == 'node':
                nodes.append(element)
            else:
                parents.append(element)

        groups: list[Sequence[Element]] = []
        for parent in parents:
            if not _check_tags_interesting(parent.tags):
                continue

            parent_members = parent.members
            if parent_members is None:
                raise AssertionError(f'Parent {parent.type}/{parent.id} members must be set')

            group: list[Element] = [parent]
            groups.append(group)
            iterate_members = [parent_members]
            while iterate_members:
                for member in iterate_members.pop():
                    member_type = member.type
                    member_id = member.id
                    member = type_ids_map.get((member_type, member_id))
                    if member is None:
                        continue
                    group.append(member)
                    if member_type == 'node':
                        member_nodes_ids.add(member_id)
                    else:
                        member_members = member.members
                        if member_members is not None:
                            iterate_members.append(member_members)

        groups.extend(
            (node,)
            for node in nodes  #
            if _check_node_interesting(node, member_nodes_ids, detailed=True)
        )
        return groups

    @staticmethod
    def filter_tags_interesting(elements: Iterable[Element]) -> tuple[Element, ...]:
        """
        Return only elements with interesting tags.
        """
        return tuple(element for element in elements if _check_tags_interesting(element.tags))


@cython.cfunc
def _check_way_area(tags: dict[str, str], members: Sequence[ElementMember]) -> cython.char:
    """
    Check if the way should be displayed as an area.
    """
    if len(members) <= 2:
        return False
    is_closed = members[0].id == members[-1].id
    if not is_closed:
        return False
    area_tags = _area_tags.intersection(tags)
    if area_tags:
        return True
    return any(key.startswith(_area_prefixes) for key in tags)


@cython.cfunc
def _check_node_interesting(node: Element, member_nodes_ids: set[ElementId], *, detailed: cython.char) -> cython.char:
    """
    Check if the node is interesting enough to be displayed.
    """
    is_member: cython.char = node.id in member_nodes_ids
    return (
        (not is_member or _check_tags_interesting(node.tags))
        if detailed
        else (not is_member and _check_tags_interesting(node.tags))
    )


@cython.cfunc
def _check_tags_interesting(tags: dict[str, str]) -> cython.char:
    """
    Check if the tags are interesting enough to be displayed.
    """
    # TODO: consider discardable tags
    # https://github.com/openstreetmap-ng/openstreetmap-ng/issues/110
    return bool(tags)


_area_tags: frozenset[str] = frozenset(
    (
        'amenity',
        'area',
        'building',
        'building:part',
        'leisure',
        'tourism',
        'ruins',
        'historic',
        'landuse',
        'military',
        'natural',
        'sport',
    )
)

_area_prefixes: tuple[str, ...] = ('area:',)
