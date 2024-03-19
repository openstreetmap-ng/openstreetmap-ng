import cython

# 64 chars to encode 6 bits
_array = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~'
_array_map = {c: i for i, c in enumerate(_array)}
_array_map['@'] = _array_map['~']  # backwards compatibility


def shortlink_encode(lon: float, lat: float, zoom: int) -> str:
    """
    Encode a coordinate pair and zoom level into a shortlink code.
    """

    x: cython.uint = int(((lon + 180) % 360) * 11930464.711111112)  # (2 ** 32) / 360
    y: cython.uint = int((lat + 90) * 23860929.422222223)  # (2 ** 32) / 180
    c: cython.ulonglong = 0
    i: cython.int

    for i in range(31, -1, -1):
        c = (c << 2) | (((x >> i) & 1) << 1) | ((y >> i) & 1)

    d: cython.int = (zoom + 8) // 3
    r: cython.int = (zoom + 8) % 3

    if r > 0:  # ceil instead of floor
        d += 1

    str_list = ['-'] * (d + r)

    for i in range(d):
        digit: cython.int = (c >> (58 - 6 * i)) & 0x3F
        str_list[i] = _array[digit]

    return ''.join(str_list)


def shortlink_decode(s: str) -> tuple[float, float, int]:
    """
    Decode a shortlink code into a coordinate pair and zoom level.

    Returns a tuple of (lon, lat, z).
    """

    x: cython.uint = 0
    y: cython.uint = 0
    z: cython.int = 0
    z_offset: cython.int = 0

    for c in s:
        t: cython.int = _array_map.get(c, -1)

        if t == -1:
            z_offset -= 1
            continue

        for _ in range(3):
            x = (x << 1) | ((t >> 5) & 1)
            y = (y << 1) | ((t >> 4) & 1)
            t <<= 2

        z += 3

    x <<= 32 - z
    y <<= 32 - z

    return (
        (
            x * 8.381903171539307e-08  # 360 / (2 ** 32)
        )
        - 180,
        (
            y * 4.190951585769653e-08  # 180 / (2 ** 32)
        )
        - 90,
        z - 8 - (z_offset % 3),
    )
