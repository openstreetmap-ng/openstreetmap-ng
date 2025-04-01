from typing import NamedTuple

import cython

from app.config import QUERY_FEATURES_RESULTS_LIMIT
from app.lib.elements_filter import ElementsFilter
from app.lib.feature_icon import FeatureIcon, features_icons
from app.lib.feature_name import features_names
from app.lib.feature_prefix import features_prefixes
from app.models.db.element import ElementInit
from app.models.element import TypedElementId, typed_element_id
from app.models.overpass import (
    OverpassElement,
    OverpassNode,
    OverpassNodeMember,
    OverpassRelation,
    OverpassWay,
    OverpassWayMember,
)


class QueryFeatureResult(NamedTuple):
    element: ElementInit
    icon: FeatureIcon | None
    prefix: str
    display_name: str | None
    geoms: list[list[tuple[float, float]]]


class QueryFeatures:
    @staticmethod
    def wrap_overpass_elements(overpass_elements: list[OverpassElement]) -> list[QueryFeatureResult]:
        id_map: dict[TypedElementId, OverpassElement] = {
            typed_element_id(element['type'], element['id']): element  #
            for element in overpass_elements
        }

        # noinspection PyTypeChecker
        elements_unfiltered: list[ElementInit] = [
            {
                'changeset_id': 0,  # type: ignore
                'typed_id': typed_id,
                'version': 0,
                'visible': True,
                'tags': element.get('tags', {}),
                'point': None,
                'members': None,
                'members_roles': None,
            }
            for typed_id, element in id_map.items()
        ]

        elements = ElementsFilter.filter_tags_interesting(elements_unfiltered)[:QUERY_FEATURES_RESULTS_LIMIT]
        if not elements:
            return []

        result: list[QueryFeatureResult] = [None] * len(elements)  # type: ignore
        geoms: list[list[tuple[float, float]]]

        i: cython.Py_ssize_t
        for i, element, icon, name, prefix in zip(
            range(len(elements)),
            elements,
            features_icons(elements),
            features_names(elements),
            features_prefixes(elements),
            strict=True,
        ):
            element_data = id_map[element['typed_id']]
            element_type = element_data['type']

            if element_type == 'node':
                node_data: OverpassNode = element_data  # type: ignore
                geoms = [[(node_data['lon'], node_data['lat'])]]

            elif element_type == 'way':
                way_data: OverpassWay = element_data  # type: ignore
                geoms = [[(point['lon'], point['lat']) for point in way_data['geometry']]]

            elif element_type == 'relation':
                relation_data: OverpassRelation = element_data  # type: ignore
                geoms = []

                for member in relation_data['members']:
                    member_type = member['type']
                    member_typed_id = typed_element_id(member_type, member['ref'])
                    member_data = id_map.get(member_typed_id)
                    if member_data is None:
                        continue

                    if member_type == 'node':
                        node_member_data: OverpassNodeMember = member_data  # type: ignore
                        geoms.append([(node_member_data['lon'], node_member_data['lat'])])

                    elif member_type == 'way':
                        way_member_data: OverpassWayMember = member_data  # type: ignore
                        geoms.append([(point['lon'], point['lat']) for point in way_member_data['geometry']])

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
