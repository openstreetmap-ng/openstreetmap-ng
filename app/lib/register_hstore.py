import struct
from typing import override

import cython
from psycopg import postgres
from psycopg._encodings import conn_encoding
from psycopg._typeinfo import TypeInfo
from psycopg.abc import AdaptContext, Buffer
from psycopg.adapt import RecursiveDumper, RecursiveLoader
from psycopg.pq import Format
from psycopg.types.hstore import HstoreLoader, _make_hstore_dumper


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
    _encoding: str

    @override
    def load(self, data: Buffer, *, unpack=struct.unpack) -> dict[str, str | None]:
        if not data:
            return {}

        view = memoryview(data)
        size: cython.uint = unpack('!I', view[:4])[0]
        if not size:
            return {}

        null_marker: cython.uint = 0xFFFFFFFF
        pos: cython.uint = 4
        result = {}

        for _ in range(size):
            key_size: cython.uint = unpack('!I', view[pos : pos + 4])[0]
            pos += 4

            key = str(view[pos : pos + key_size], 'utf-8')
            pos += key_size

            value_size: cython.uint = unpack('!I', view[pos : pos + 4])[0]
            pos += 4

            if value_size == null_marker:
                value = None
            else:
                value = str(view[pos : pos + value_size], 'utf-8')
                pos += value_size

            result[key] = value

        return result


def _make_hstore_binary_loader(oid_in: int, encoding: str) -> type[HstoreBinaryLoader]:
    attribs = {'_encoding': encoding}
    return type(f'HstoreBinaryLoader{oid_in}', (HstoreBinaryLoader,), attribs)


class HstoreBinaryDumper(RecursiveDumper):
    format = Format.BINARY
    _encoding: str

    @override
    def dump(self, obj: dict[str, str | None], *, pack_into=struct.pack_into) -> Buffer | None:
        if not obj:
            return b'\x00\x00\x00\x00'

        pos: cython.uint = 4
        encoding = self._encoding
        encoded: list[tuple[bytes, bytes | None]] = []

        for key, value in obj.items():
            key_bytes = key.encode(encoding)
            pos += 4 + len(key_bytes)

            if value is None:
                value_bytes = None
                pos += 4
            else:
                value_bytes = value.encode(encoding)
                pos += 4 + len(value_bytes)

            encoded.append((key_bytes, value_bytes))

        buffer = bytearray(pos)
        pack_into('>I', buffer, 0, len(obj))
        pos = 4

        for key_bytes, value_bytes in encoded:
            key_len: cython.Py_ssize_t = len(key_bytes)
            pack_into('>I', buffer, pos, key_len)
            pos += 4

            buffer[pos : pos + key_len] = key_bytes
            pos += key_len

            if value_bytes is None:
                pack_into('>I', buffer, pos, 0xFFFFFFFF)
                pos += 4
            else:
                value_len: cython.Py_ssize_t = len(value_bytes)
                pack_into('>I', buffer, pos, value_len)
                pos += 4

                buffer[pos : pos + value_len] = value_bytes
                pos += value_len

        return buffer


def _make_hstore_binary_dumper(oid_in: int, encoding: str) -> type[HstoreBinaryDumper]:
    attribs = {'oid_in': oid_in, '_encoding': encoding}
    return type(f'HstoreBinaryDumper{oid_in}', (HstoreBinaryDumper,), attribs)
