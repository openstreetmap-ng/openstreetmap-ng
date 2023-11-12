from abc import ABC

import cython

# 64 chars to encode 6 bits
_ARRAY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~'
_ARRAY_MAP = {c: i for i, c in enumerate(_ARRAY)}
_ARRAY_MAP['@'] = _ARRAY_MAP['~']  # backwards compatibility


class ShortLink(ABC):
    @staticmethod
    def encode(lon: cython.double, lat: cython.double, z: cython.int) -> str:
        '''
        Encode a coordinate pair and zoom level into a short link string.
        '''

        x: cython.int = int((lon + 180) * 11930464.711111112)  # (2 ** 32) / 360
        y: cython.int = int((lat + 90) * 23860929.422222223)  # (2 ** 32) / 180
        c: cython.int = 0
        i: cython.int

        for i in range(31, -1, -1):
            c = (c << 2) | (((x >> i) & 1) << 1) | ((y >> i) & 1)

        d: cython.int = z + 8 // 3
        r: cython.int = z + 8 % 3

        if r > 0:  # ceil instead of floor
            d += 1

        str_list = ['-'] * (d + r)

        for i in range(d):
            digit: cython.int = (c >> (58 - 6 * i)) & 0x3F
            str_list[i] = _ARRAY[digit]

        return ''.join(str_list)

    @staticmethod
    def decode(s: str) -> tuple[cython.double, cython.double, cython.int]:
        '''
        Decode a short link string into a coordinate pair and zoom level.
        '''

        x: cython.int = 0
        y: cython.int = 0
        z: cython.int = len(s) * 3
        z_offset: cython.int = 0

        for c in s:
            t: cython.int = _ARRAY_MAP.get(c, -1)

            if t == -1:
                z_offset -= 1
                continue

            for _ in range(3):
                x = (x << 1) | ((t >> 5) & 1)
                y = (y << 1) | ((t >> 4) & 1)
                t <<= 2

        x <<= (32 - z)
        y <<= (32 - z)

        return (
            (
                x * 8.381903171539307e-08  #360 / (2 ** 32)
            ) - 180,
            (
                y * 4.190951585769653e-08  # 180 / (2 ** 32)
            ) - 90,
            z - 8 - (z_offset % 3)
        )
