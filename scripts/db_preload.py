import pathlib

import anyio
import lxml.etree as ET
from shapely import Point

from app.models.db import *  # noqa: F403
from app.models.db.element import Element
from app.models.element_member import ElementMemberRef
from app.models.element_type import ElementType


async def main():
    preload_path = pathlib.Path(__file__).parent.parent / 'preload.osm'
    if not preload_path.is_file():
        raise FileNotFoundError('File not found: ' + preload_path)

    with preload_path.open('rb') as f:
        context = ET.iterparse(f)
        elem: ET.ElementBase
        temp_tags = {}
        temp_members = []

        # tag {'k': 'historic', 'v': 'memorial'}
        # node {'id': '2', 'version': '20', 'timestamp': '2017-05-12T20:38:36Z', 'uid': '362126', 'user': 'Зелёный Кошак', 'changeset': '48634891', 'lat': '59.7718083', 'lon': '30.3260539'}

        for _, elem in context:
            if elem.tag == 'tag':
                temp_tags[elem.attrib['k']] = elem.attrib['v']
            elif elem.tag in ('nd', 'member'):
                temp_members.append(
                    ElementMemberRef(
                        type=ElementType.from_str(elem.attrib['type']),
                        typed_id=int(elem.attrib['ref']),
                        role=elem.attrib.get('role', ''),
                    )
                )
            elif elem.tag in ('node', 'way', 'relation'):
                # TODO: create user, changeset
                if elem.tag == 'node' and (lon := elem.attrib.get('lon')) and (lat := elem.attrib.get('lat')):
                    point = Point(float(lon), float(lat))
                else:
                    point = None

                element = Element(
                    user_id=int(elem.attrib['uid']),
                    changeset_id=int(elem.attrib['changeset']),
                    type=ElementType.from_str(elem.tag),
                    typed_id=int(elem.attrib['id']),
                    version=int(elem.attrib['version']),
                    visible=elem.attrib.get('visible', 'true') == 'true',
                    tags=temp_tags,
                    point=point,
                    members=temp_members,
                )
                temp_tags = {}
                temp_members = []


if __name__ == '__main__':
    anyio.run(main, backend_options={'use_uvloop': True})
