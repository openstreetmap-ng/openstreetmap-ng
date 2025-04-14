from struct import Struct
from typing import override

import cython
from psycopg import postgres
from psycopg._encodings import conn_encoding
from psycopg._typeinfo import TypeInfo
from psycopg.abc import AdaptContext, Buffer
from psycopg.adapt import RecursiveDumper, RecursiveLoader
from psycopg.pq import Format
from psycopg.types.hstore import HstoreLoader, _make_hstore_dumper

_U32_STRUCT = Struct('!I')
"""Simple struct representing an unsigned 32-bit big-endian integer."""

_I2B = [i.to_bytes(4) for i in range(256)]
"""Lookup list for small ints to bytes conversions."""


def register_hstore(info: TypeInfo, context: AdaptContext | None = None) -> None:
    """Register the adapters to load and dump hstore."""
    adapters = context.adapters if context is not None else postgres.adapters
    encoding = conn_encoding(context.connection if context is not None else None)
    info.register(context)

    adapters.register_dumper(dict, _make_hstore_dumper(info.oid))
    adapters.register_dumper(dict, _make_hstore_binary_dumper(info.oid, encoding))

    adapters.register_loader(info.oid, HstoreLoader)
    adapters.register_loader(info.oid, _make_hstore_binary_loader(info.oid, encoding))


class HstoreBinaryLoader(RecursiveLoader):
    format = Format.BINARY
    encoding: str

    @override
    def load(self, data: Buffer) -> dict[str, str | None]:
        if len(data) < 12:  # Fast-path if too small to contain any data.
            return {}

        unpack_from = _U32_STRUCT.unpack_from
        encoding = self.encoding
        null_marker: cython.uint = 0xFFFFFFFF
        result = {}

        view = bytes(data)
        size: cython.uint = unpack_from(view)[0]
        pos: cython.uint = 4

        for _ in range(size):
            key_size: cython.uint = unpack_from(view, pos)[0]
            pos += 4

            key = view[pos : pos + key_size].decode(encoding)
            pos += key_size

            value_size: cython.uint = unpack_from(view, pos)[0]
            pos += 4

            if value_size == null_marker:
                value = None
            else:
                value = view[pos : pos + value_size].decode(encoding)
                pos += value_size

            result[key] = value

        return result


def _make_hstore_binary_loader(oid_in: int, encoding: str) -> type[HstoreBinaryLoader]:
    attribs = {'encoding': encoding}
    return type(f'HstoreBinaryLoader{oid_in}', (HstoreBinaryLoader,), attribs)


class HstoreBinaryDumper(RecursiveDumper):
    format = Format.BINARY
    encoding: str

    @override
    def dump(self, obj: dict[str, str | None]) -> Buffer:
        if not obj:
            return b'\x00\x00\x00\x00'

        i2b: list[bytes] = _I2B
        encoding = self.encoding
        buffer: list[bytes] = [i2b[i] if (i := len(obj)) < 256 else i.to_bytes(4)]

        for key, value in obj.items():
            key_bytes = key.encode(encoding)
            buffer.append(i2b[i] if (i := len(key_bytes)) < 256 else i.to_bytes(4))  # noqa: FURB113
            buffer.append(key_bytes)

            if value is None:
                buffer.append(b'\xff\xff\xff\xff')
            else:
                value_bytes = value.encode(encoding)
                buffer.append(  # noqa: FURB113
                    i2b[i] if (i := len(value_bytes)) < 256 else i.to_bytes(4)
                )
                buffer.append(value_bytes)

        return b''.join(buffer)


def _make_hstore_binary_dumper(oid_in: int, encoding: str) -> type[HstoreBinaryDumper]:
    attribs = {'oid_in': oid_in, 'encoding': encoding}
    return type(f'HstoreBinaryDumper{oid_in}', (HstoreBinaryDumper,), attribs)
