from io import BytesIO

from PIL import Image

from app.db import db_fetchrows
from app.lib.geo.gps_tiles import GPS_MASTER_ZOOM, GPS_TILE_SIZE


class GPSTileQuery:
    @staticmethod
    async def render(z: int, x: int, y: int) -> bytes:
        left = x * GPS_TILE_SIZE
        top = y * GPS_TILE_SIZE
        right = left + GPS_TILE_SIZE
        bottom = top + GPS_TILE_SIZE
        table = 'gps_pixel' if z == GPS_MASTER_ZOOM else 'gps_pixel_overview'
        zoom_filter = t'' if z == GPS_MASTER_ZOOM else t'AND zoom = {z}'
        pixels = await db_fetchrows(t"""
            SELECT x - {left}, y - {top}
            FROM {table:i}
            WHERE x >= {left} AND x < {right}
                AND y >= {top} AND y < {bottom} AND count > 0
                {zoom_filter:q}
        """)
        image = Image.new('RGBA', (GPS_TILE_SIZE, GPS_TILE_SIZE))
        for px, py in pixels:
            image.putpixel((px, py), (0, 80, 255, 255))
        output = BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()
