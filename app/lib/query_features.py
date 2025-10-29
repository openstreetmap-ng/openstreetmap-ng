from typing import NamedTuple

from shapely.geometry.base import BaseGeometry

from app.config import QUERY_FEATURES_RESULTS_LIMIT
from app.lib.elements_filter import ElementsFilter
from app.lib.feature_icon import FeatureIcon, features_icons
from app.lib.feature_name import features_names
from app.lib.feature_prefix import features_prefixes
from app.models.db.element import ElementInit
from app.models.db.element_spatial import ElementSpatial
from app.models.element import TypedElementId


class QueryFeatureResult(NamedTuple):
    element: ElementInit
    icon: FeatureIcon | None
    prefix: str
    display_name: str | None
    geometry: BaseGeometry


class QueryFeatures:
    @staticmethod
    def wrap_element_spatial(
        spatial_elements: list[ElementSpatial],
    ) -> list[QueryFeatureResult]:
        """Wrap element_spatial query results into QueryFeatureResult format."""
        if not spatial_elements:
            return []

        elements: list[ElementInit] = [
            {
                'changeset_id': 0,  # type: ignore
                'typed_id': el['typed_id'],
                'version': el['version'],
                'visible': True,
                'tags': el['tags'],
                'point': None,
                'members': None,
                'members_roles': None,
            }
            for el in spatial_elements
        ]

        # Filter interesting tags and apply limit
        elements = ElementsFilter.filter_tags_interesting(elements)
        if not elements:
            return []

        elements = elements[:QUERY_FEATURES_RESULTS_LIMIT]

        spatial_map: dict[TypedElementId, ElementSpatial]
        spatial_map = {el['typed_id']: el for el in spatial_elements}

        return [
            QueryFeatureResult(
                element=element,
                icon=icon,
                prefix=prefix,
                display_name=name,
                geometry=spatial_map[element['typed_id']]['geom'],
            )
            for element, icon, name, prefix in zip(
                elements,
                features_icons(elements),
                features_names(elements),
                features_prefixes(elements),
                strict=True,
            )
        ]
