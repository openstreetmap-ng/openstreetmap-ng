from collections.abc import Iterable, Sequence
from typing import NamedTuple

import cython

from app.lib.elements_filter import ElementsFilter
from app.lib.feature_icon import FeatureIcon, features_icons
from app.lib.feature_name import features_names
from app.lib.feature_prefix import features_prefixes
from app.limits import QUERY_FEATURES_RESULTS_LIMIT
from app.models.db.element import Element
from app.models.element import ElementId, ElementType
from app.models.overpass import (
    OverpassElement,
    OverpassNode,
    OverpassNodeMember,
    OverpassRelation,
    OverpassWay,
    OverpassWayMember,
)


class QueryFeatureResult(NamedTuple):
    element: Element
    icon: FeatureIcon | None
    prefix: str
    display_name: str | None
    geoms: Sequence[Sequence[tuple[float, float]]]


class QueryFeatures:
    @staticmethod
    def wrap_overpass_elements(overpass_elements: Iterable[OverpassElement]) -> list[QueryFeatureResult]:
        type_id_map: dict[tuple[ElementType, ElementId], OverpassElement] = {
            (element['type'], element['id']): element  #
            for element in overpass_elements
        }

        elements_unfiltered: list[Element] = [None] * len(type_id_map)  # type: ignore
        i: cython.int
        for i, element in enumerate(type_id_map.values()):
            elements_unfiltered[i] = Element(
                changeset_id=0,
                type=element['type'],
                id=element['id'],
                version=0,
                visible=True,
                tags=element.get('tags', {}),
                point=None,
            )

        elements = ElementsFilter.filter_tags_interesting(elements_unfiltered)[:QUERY_FEATURES_RESULTS_LIMIT]
        icons = features_icons(elements)
        names = features_names(elements)
        prefixes = features_prefixes(elements)

        result: list[QueryFeatureResult] = [None] * len(elements)  # type: ignore
        for i, element, icon, name, prefix in zip(range(len(elements)), elements, icons, names, prefixes, strict=True):
            element_type = element.type
            element_data = type_id_map[(element_type, element.id)]
            if element_type == 'node':
                node_data: OverpassNode = element_data  # pyright: ignore[reportAssignmentType]
                geoms = (((node_data['lon'], node_data['lat']),),)
            elif element_type == 'way':
                way_data: OverpassWay = element_data  # pyright: ignore[reportAssignmentType]
                geoms = (tuple((point['lon'], point['lat']) for point in way_data['geometry']),)
            elif element_type == 'relation':
                relation_data: OverpassRelation = element_data  # pyright: ignore[reportAssignmentType]
                geoms_list: list[tuple[tuple[float, float], ...]] = []
                for member in relation_data['members']:
                    member_type = member['type']
                    member_data = type_id_map.get((member_type, member['ref']))
                    if member_data is None:
                        continue
                    if member_type == 'node':
                        node_member_data: OverpassNodeMember = member_data  # pyright: ignore[reportAssignmentType]
                        geoms_list.append(((node_member_data['lon'], node_member_data['lat']),))
                    elif member_type == 'way':
                        way_member_data: OverpassWayMember = member_data  # pyright: ignore[reportAssignmentType]
                        geoms_list.append(tuple((point['lon'], point['lat']) for point in way_member_data['geometry']))
                geoms = geoms_list
            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')
            result[i] = QueryFeatureResult(
                element=element,
                icon=icon,
                prefix=prefix,
                display_name=name,
                geoms=geoms,
            )
        return result
