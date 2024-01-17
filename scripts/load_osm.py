import sys
from datetime import datetime
from pathlib import Path

import xmltodict
from anyio import to_thread
from shapely.geometry import Point

from src.lib.format.format06 import Format06
from src.lib_cython.xmltodict import XMLToDict
from src.models.db.element import Element
from src.models.db.element_node import ElementNode
from src.models.db.element_relation import ElementRelation
from src.models.db.element_way import ElementWay
from src.models.element_member import ElementMemberRef
from src.models.element_type import ElementType
from src.models.typed_element_ref import TypedElementRef


async def main():
    load_path = Path(sys.argv[1])
    print(f'Loading {load_path} into database...')

    def thread():
        batch = []
        total = 0

        async def process_batch():
            nonlocal batch
            nonlocal total
            batch_ = batch
            batch = []
            total += len(batch_)
            print(f'Processing batch of {len(batch_)} elements (total {total})')
            await Element._collection().bulk_write(batch_, ordered=False)

        def item_callback(tree, body):
            if not isinstance(body, dict):
                body = {}

            element_type, element = tree[-1]

            if element_type not in ('node', 'way', 'relation'):
                return True

            base = {
                'typed_id': int(element['id']),
                'changeset_id': int(element['changeset']),
                'created_at': datetime.fromisoformat(element['timestamp']),
                'version': int(element['version']),
                'visible': element.get('visible', True),
                'tags': Format06._decode_tags_unsafe(body.get('tag', [])),
            }

            if element_type == 'node':
                if 'lon' not in element:
                    lon = 0
                    lat = 0
                else:
                    lon = float(element['lon'])
                    lat = float(element['lat'])

                batch.append(ElementNode(**base, point=Point(lon, lat)).create_batch())

            elif element_type == 'way':
                if 'nd' not in body:
                    body['nd'] = []

                batch.append(ElementWay(**base, nodes=tuple(n['@ref'] for n in body['nd'])).create_batch())

            elif element_type == 'relation':
                if 'member' not in body:
                    body['member'] = []

                batch.append(
                    ElementRelation(
                        **base,
                        members=tuple(
                            ElementMemberRef(
                                ref=TypedElementRef(
                                    type=ElementType(m['@type']),
                                    typed_id=m['@ref'],
                                ),
                                role=m['@role'],
                            )
                            for m in body['member']
                        ),
                    ).create_batch()
                )

            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')

            if len(batch) >= 10000:
                anyio.from_thread.run(process_batch)

            return True

        xmltodict.parse(
            load_path.open('rb'),
            force_list=XMLToDict.force_list,
            postprocessor=XMLToDict.postprocessor,
            item_depth=2,
            item_callback=item_callback,
        )

        if batch:
            anyio.from_thread.run(process_batch)

    await to_thread.run_sync(thread)

    # TODO: fixup latest
    # TODO: fixup sequence


if __name__ == '__main__':
    anyio.run(main)
