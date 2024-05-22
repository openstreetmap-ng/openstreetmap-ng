from app.format.leaflet_element import LeafletElementMixin
from app.format.leaflet_note import LeafletNoteMixin


class FormatLeaflet(
    LeafletElementMixin,
    LeafletNoteMixin,
): ...
