from abc import ABC

# 64 chars to encode 6 bits
_ARRAY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~'
_ARRAY_MAP = {c: i for i, c in enumerate(_ARRAY)}
_ARRAY_MAP['@'] = _ARRAY_MAP['~']  # backwards compatibility


class ShortLink(ABC):
    @staticmethod
    def encode(lon: float, lat: float, z: int) -> str:
        '''
        Encode a coordinate pair and zoom level into a short link string.
        '''

        x = int((lon + 180) * (2 ** 32) / 360)
        y = int((lat + 90) * (2 ** 32) / 180)

        c = 0

        for i in range(31, -1, -1):
            c = (c << 2) | (((x >> i) & 1) << 1) | ((y >> i) & 1)

        d, r = divmod(z + 8, 3)

        if r > 0:  # ceil instead of floor
            d += 1

        str_list = ['-'] * (d + r)

        for i in range(d):
            digit = (c >> (58 - 6 * i)) & 0x3F
            str_list[i] = _ARRAY[digit]

        return ''.join(str_list)

    @staticmethod
    def decode(s: str) -> tuple[float, float, int]:
        '''
        Decode a short link string into a coordinate pair and zoom level.
        '''

        x, y = 0, 0
        z = len(s) * 3
        z_offset = 0

        for c in s:
            if (t := _ARRAY_MAP.get(c, None)) is None:
                z_offset -= 1
                continue

            for _ in range(3):
                x = (x << 1) | ((t >> 5) & 1)
                y = (y << 1) | ((t >> 4) & 1)
                t <<= 2

        x <<= (32 - z)
        y <<= (32 - z)

        return (
            (x * 360 / (2 ** 32)) - 180,
            (y * 180 / (2 ** 32)) - 90,
            z - 8 - (z_offset % 3)
        )
