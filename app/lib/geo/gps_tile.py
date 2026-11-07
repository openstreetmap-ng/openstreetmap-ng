from io import BytesIO
from math import atan, degrees, log, pi, radians, sinh, tan

from PIL import Image, ImageDraw
from shapely import LineString, Polygon, box, set_srid

GPS_TILE_SIZE = 256
GPS_TILE_MAX_ZOOM = 20
_MAX_LATITUDE = degrees(atan(sinh(pi)))


def gps_tile_bounds(z: int, x: int, y: int) -> Polygon:
    """Include a two-pixel gutter so strokes are continuous at tile edges."""
    n = 1 << z
    pad = 2 / GPS_TILE_SIZE
    west = (x - pad) / n * 360 - 180
    east = (x + 1 + pad) / n * 360 - 180
    north = degrees(atan(sinh(pi * (1 - 2 * (y - pad) / n))))
    south = degrees(atan(sinh(pi * (1 - 2 * (y + 1 + pad) / n))))
    return set_srid(box(west, south, east, north), 4326)


def render_gps_tile(lines: list[LineString], z: int, x: int, y: int) -> bytes:
    """Rasterize clipped, unwrapped segments without joining separate tracks."""
    scale = 2
    image = Image.new('RGBA', (GPS_TILE_SIZE * scale,) * 2)
    draw = ImageDraw.Draw(image)
    world = GPS_TILE_SIZE * (1 << z)
    for line in lines:
        points = []
        for lon, lat in line.coords:
            lat = max(-_MAX_LATITUDE, min(_MAX_LATITUDE, lat))
            px = ((lon + 180) / 360 * world - x * GPS_TILE_SIZE) * scale
            py = (
                (1 - log(tan(pi / 4 + radians(lat) / 2)) / pi) / 2 * world
                - y * GPS_TILE_SIZE
            ) * scale
            points.append((px, py))
        if len(points) >= 2:
            draw.line(points, fill=(238, 0, 238, 200), width=2 * scale)
    image = image.resize((GPS_TILE_SIZE,) * 2, Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
