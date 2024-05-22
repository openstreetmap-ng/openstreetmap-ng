from app.format.api07_element import Element07Mixin
from app.format.leaflet_element import LeafletElementMixin
from app.format.leaflet_note import LeafletNoteMixin


class Format07(
    Element07Mixin,
): ...


class FormatLeaflet(
    LeafletElementMixin,
    LeafletNoteMixin,
): ...
