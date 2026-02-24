from __future__ import annotations

import inspect
import keyword
import math
import sys
import types
import typing
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from typing import (
    Any,
    ForwardRef,
    get_args,
    get_origin,
    get_overloads,
    get_protocol_members,
)

import protoc_gen_pyi_wkt_augments as _wkt_augments
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.compiler import plugin_pb2

_SCALAR_TYPE: dict[int, str] = {
    descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE: 'float',
    descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT: 'float',
    descriptor_pb2.FieldDescriptorProto.TYPE_INT64: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT64: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_INT32: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_BOOL: 'bool',
    descriptor_pb2.FieldDescriptorProto.TYPE_STRING: 'str',
    descriptor_pb2.FieldDescriptorProto.TYPE_BYTES: 'bytes',
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT32: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT32: 'int',
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT64: 'int',
}

def _scalar_rule_branch(field_type: int):
    if field_type not in _SCALAR_TYPE:
        return None
    field_type_name = descriptor_pb2.FieldDescriptorProto.Type.Name(field_type)
    return field_type_name[5:].lower()


@dataclass(frozen=True)
class _EnumMeta:
    syntax: str
    numbers: tuple[int, ...]
    names_by_number: dict[int, tuple[str, ...]]


@dataclass(frozen=True)
class _ValueSubset:
    in_values: tuple[object, ...] | None = None
    not_in_values: tuple[object, ...] = ()
    defined_only: bool = False


def _has_field(message: object, field_name: str):
    try:
        return bool(message.HasField(field_name))
    except ValueError:
        return False


def _proto_to_module(proto_path: str, *, suffix: str):
    # protoc's python generator derives module name from proto file path.
    # Example: app/models/proto/shared.proto -> app.models.proto.shared_pb2
    if not proto_path.endswith('.proto'):
        return proto_path.replace('/', '.')
    return proto_path[:-6].replace('/', '.') + suffix

def _proto_to_output_path(proto_path: str, *, paths: str, suffix: str):
    # We only support source-relative output paths.
    if paths != 'source_relative':
        raise ValueError(f'Unsupported paths mode: {paths!r}')
    if not proto_path.endswith('.proto'):
        raise ValueError(f'Unexpected proto path (expected .proto): {proto_path!r}')
    output = proto_path[:-6] + suffix

    # google.protobuf's generated modules live in site-packages, but the
    # protobuf package doesn't ship `.pyi` files for them. Put stubs under
    # `typings/` so Pyright can pick them up without affecting runtime imports.
    if proto_path.startswith('google/protobuf/'):
        return f'typings/{output}'
    return output


def _escape_ident(name: str):
    if keyword.iskeyword(name):
        raise ValueError(
            f'Cannot generate stubs for Python keyword identifier: {name!r}. '
            'Rename it in the .proto (protobuf Python exposes keyword-named '
            'fields via getattr only, which is not representable in .pyi).'
        )
    return name


def _escape_field_ident(name: str):
    # Protobuf Python doesn't rename keyword field names, which makes them
    # unrepresentable as normal attributes in .pyi files. We still allow such
    # fields to exist (e.g. protovalidate uses "in"), but we can't emit
    # attribute stubs for them.
    return None if keyword.iskeyword(name) else name


@dataclass(frozen=True)
class _Symbol:
    proto_name: str  # fully-qualified, leading dot
    file_name: str  # proto file path
    python_qualname: str  # Outer.Inner or Top


@dataclass(frozen=True)
class _EnumDef:
    proto_name: str  # fully-qualified, leading dot
    symbol: _Symbol
    enum: descriptor_pb2.EnumDescriptorProto


def _enum_alias_prefix(enum_sym: _Symbol):
    return enum_sym.python_qualname.replace('.', '_')


def _build_symbol_table(
    protos: Iterable[descriptor_pb2.FileDescriptorProto],
):
    out: dict[str, _Symbol] = {}

    def add_enum(
        *,
        file_name: str,
        parent_proto: str,
        parent_py: str,
        enum: descriptor_pb2.EnumDescriptorProto,
    ):
        proto_name = f'{parent_proto}.{enum.name}'
        python_qualname = (
            f'{parent_py}.{enum.name}' if parent_py else _escape_ident(enum.name)
        )
        out[proto_name] = _Symbol(
            proto_name=proto_name,
            file_name=file_name,
            python_qualname=python_qualname,
        )

    def add_message(
        *,
        file_name: str,
        parent_proto: str,
        parent_py: str,
        msg: descriptor_pb2.DescriptorProto,
    ):
        proto_name = f'{parent_proto}.{msg.name}'
        python_qualname = (
            f'{parent_py}.{msg.name}' if parent_py else _escape_ident(msg.name)
        )
        out[proto_name] = _Symbol(
            proto_name=proto_name,
            file_name=file_name,
            python_qualname=python_qualname,
        )

        for enum in msg.enum_type:
            add_enum(
                file_name=file_name,
                parent_proto=proto_name,
                parent_py=python_qualname,
                enum=enum,
            )

        for nested in msg.nested_type:
            # Map entry messages are internal implementation detail; we still add
            # them to the symbol table so map fields can resolve type names.
            add_message(
                file_name=file_name,
                parent_proto=proto_name,
                parent_py=python_qualname,
                msg=nested,
            )

    for f in protos:
        package = f'.{f.package}' if f.package else ''
        for enum in f.enum_type:
            add_enum(file_name=f.name, parent_proto=package, parent_py='', enum=enum)
        for msg in f.message_type:
            add_message(file_name=f.name, parent_proto=package, parent_py='', msg=msg)

    return out


def _build_enum_meta_table(
    protos: Iterable[descriptor_pb2.FileDescriptorProto],
):
    out: dict[str, _EnumMeta] = {}

    def add_enum(
        *,
        syntax: str,
        parent_proto: str,
        enum: descriptor_pb2.EnumDescriptorProto,
    ):
        proto_name = f'{parent_proto}.{enum.name}'
        numbers = tuple(dict.fromkeys(v.number for v in enum.value))
        names_by_number: dict[int, list[str]] = {}
        for v in enum.value:
            names_by_number.setdefault(v.number, []).append(v.name)
        out[proto_name] = _EnumMeta(
            syntax=syntax,
            numbers=numbers,
            names_by_number={k: tuple(vs) for k, vs in names_by_number.items()},
        )

    def walk_message(
        *,
        syntax: str,
        parent_proto: str,
        msg: descriptor_pb2.DescriptorProto,
    ):
        msg_proto = f'{parent_proto}.{msg.name}'
        for enum in msg.enum_type:
            add_enum(syntax=syntax, parent_proto=msg_proto, enum=enum)
        for nested in msg.nested_type:
            walk_message(syntax=syntax, parent_proto=msg_proto, msg=nested)

    for f in protos:
        syntax = f.syntax or 'proto2'
        package = f'.{f.package}' if f.package else ''
        for enum in f.enum_type:
            add_enum(syntax=syntax, parent_proto=package, enum=enum)
        for msg in f.message_type:
            walk_message(syntax=syntax, parent_proto=package, msg=msg)

    return out


def _iter_file_enums(
    *,
    file_proto: descriptor_pb2.FileDescriptorProto,
    symbols: dict[str, _Symbol],
):
    def walk_message(
        *,
        parent_proto: str,
        msg: descriptor_pb2.DescriptorProto,
    ):
        msg_proto = f'{parent_proto}.{msg.name}'
        for enum in msg.enum_type:
            enum_proto = f'{msg_proto}.{enum.name}'
            enum_sym = symbols[enum_proto]
            yield _EnumDef(proto_name=enum_proto, symbol=enum_sym, enum=enum)

        for nested in msg.nested_type:
            yield from walk_message(parent_proto=msg_proto, msg=nested)

    package = f'.{file_proto.package}' if file_proto.package else ''

    for enum in file_proto.enum_type:
        enum_proto = f'{package}.{enum.name}'
        enum_sym = symbols[enum_proto]
        yield _EnumDef(proto_name=enum_proto, symbol=enum_sym, enum=enum)

    for msg in file_proto.message_type:
        yield from walk_message(parent_proto=package, msg=msg)


def _file_has_enums(file_proto: descriptor_pb2.FileDescriptorProto):
    def message_has_enums(msg: descriptor_pb2.DescriptorProto):
        return bool(msg.enum_type) or any(message_has_enums(n) for n in msg.nested_type)

    return bool(file_proto.enum_type) or any(
        message_has_enums(msg) for msg in file_proto.message_type
    )


_REPEATED_COMPOSITE_PROTO_SUPPORT = (
    'class _RepeatedComposite(Protocol[_TMessage]):',
    '    def add(self, **kwargs: Any) -> _TMessage: ...',
    '    def append(self, value: _TMessage) -> None: ...',
    '    def extend(self, values: Iterable[_TMessage]) -> None: ...',
    '    def insert(self, index: int, value: _TMessage) -> None: ...',
    '    def remove(self, value: _TMessage) -> None: ...',
    '    def pop(self, index: int = -1) -> _TMessage: ...',
    '    def clear(self) -> None: ...',
    '    def reverse(self) -> None: ...',
    '    def sort(self, *, key: Callable[[_TMessage], Any] | None = ..., reverse: bool = ...) -> None: ...',
    '    def MergeFrom(self, other: Iterable[_TMessage]) -> None: ...',
    '    def __len__(self) -> int: ...',
    '    def __iter__(self) -> Iterator[_TMessage]: ...',
    '    @overload',
    '    def __getitem__(self, index: int) -> _TMessage: ...',
    '    @overload',
    '    def __getitem__(self, index: slice) -> list[_TMessage]: ...',
    '    @overload',
    '    def __delitem__(self, index: int) -> None: ...',
    '    @overload',
    '    def __delitem__(self, index: slice) -> None: ...',
)

_REPEATED_SCALAR_PROTO_SUPPORT = (
    'class _RepeatedScalar(MutableSequence[_TScalar], Protocol[_TScalar]):',
    '    def append(self, value: _TScalar) -> None: ...',
    '    def extend(self, values: Iterable[_TScalar]) -> None: ...',
    '    def insert(self, index: int, value: _TScalar) -> None: ...',
    '    def remove(self, value: _TScalar) -> None: ...',
    '    def pop(self, index: int = -1) -> _TScalar: ...',
    '    def clear(self) -> None: ...',
    '    def reverse(self) -> None: ...',
    '    def sort(self, *, key: Callable[[_TScalar], Any] | None = ..., reverse: bool = ...) -> None: ...',
    '    def MergeFrom(self, other: Iterable[_TScalar]) -> None: ...',
    '    def __len__(self) -> int: ...',
    '    def __iter__(self) -> Iterator[_TScalar]: ...',
    '    @overload',
    '    def __getitem__(self, index: int) -> _TScalar: ...',
    '    @overload',
    '    def __getitem__(self, index: slice) -> list[_TScalar]: ...',
    '    @overload',
    '    def __setitem__(self, index: int, value: _TScalar) -> None: ...',
    '    @overload',
    '    def __setitem__(self, index: slice, value: Iterable[_TScalar]) -> None: ...',
    '    @overload',
    '    def __delitem__(self, index: int) -> None: ...',
    '    @overload',
    '    def __delitem__(self, index: slice) -> None: ...',
    '    def __contains__(self, value: object) -> bool: ...',
)

_REPEATED_ENUM_PROTO_SUPPORT = (
    'class _RepeatedEnum(MutableSequence[int], Protocol[_TEnumParam, _TEnumValue]):',
    '    def append(self, value: _TEnumParam) -> None: ...',
    '    def extend(self, values: Iterable[_TEnumParam]) -> None: ...',
    '    def insert(self, index: int, value: _TEnumParam) -> None: ...',
    '    def remove(self, value: int) -> None: ...',
    '    def pop(self, index: int = -1) -> _TEnumValue: ...',
    '    def clear(self) -> None: ...',
    '    def reverse(self) -> None: ...',
    '    def sort(self, *, key: Callable[[_TEnumValue], Any] | None = ..., reverse: bool = ...) -> None: ...',
    '    def MergeFrom(self, other: Iterable[_TEnumParam]) -> None: ...',
    '    def __len__(self) -> int: ...',
    '    def __iter__(self) -> Iterator[_TEnumValue]: ...',
    '    @overload',
    '    def __getitem__(self, index: int) -> _TEnumValue: ...',
    '    @overload',
    '    def __getitem__(self, index: slice) -> list[_TEnumValue]: ...',
    '    @overload',
    '    def __setitem__(self, index: int, value: _TEnumParam) -> None: ...',
    '    @overload',
    '    def __setitem__(self, index: slice, value: Iterable[_TEnumParam]) -> None: ...',
    '    @overload',
    '    def __delitem__(self, index: int) -> None: ...',
    '    @overload',
    '    def __delitem__(self, index: slice) -> None: ...',
    '    def __contains__(self, value: object) -> bool: ...',
)

_MESSAGE_MAP_PROTO_SUPPORT = (
    'class _MessageMap(Mapping[_K, _TMessage], Protocol[_K, _TMessage]):',
    '    def get_or_create(self, key: _K) -> _TMessage: ...',
    '    def __delitem__(self, key: _K) -> None: ...',
    '    def pop(self, key: _K) -> _TMessage: ...',
    '    def clear(self) -> None: ...',
    '    def MergeFrom(self, other: _MessageMap[_K, _TMessage]) -> None: ...',
)


class _Protovalidate:
    def __init__(self, request: plugin_pb2.CodeGeneratorRequest):
        pool = descriptor_pool.DescriptorPool()

        pending = list(request.proto_file)
        while pending:
            next_pending: list[descriptor_pb2.FileDescriptorProto] = []
            progressed = False
            for f in pending:
                try:
                    pool.Add(f)
                except TypeError:
                    next_pending.append(f)
                else:
                    progressed = True

            if not progressed:
                break

            pending = next_pending

        try:
            self._field_ext = pool.FindExtensionByName('buf.validate.field')
        except KeyError:
            self._field_ext = None

        try:
            self._oneof_ext = pool.FindExtensionByName('buf.validate.oneof')
        except KeyError:
            self._oneof_ext = None

        try:
            opts_desc = pool.FindMessageTypeByName('google.protobuf.FieldOptions')
        except KeyError:
            self._field_options_cls = None
        else:
            self._field_options_cls = message_factory.GetMessageClass(opts_desc)

        try:
            opts_desc = pool.FindMessageTypeByName('google.protobuf.OneofOptions')
        except KeyError:
            self._oneof_options_cls = None
        else:
            self._oneof_options_cls = message_factory.GetMessageClass(opts_desc)

    def _field_rules(self, field: descriptor_pb2.FieldDescriptorProto):
        if self._field_ext is None or self._field_options_cls is None:
            return None

        opts = self._field_options_cls()
        opts.ParseFromString(field.options.SerializeToString())

        # Extensions show up as unknown fields unless the pool knows them.
        if self._field_ext not in opts.Extensions:
            return None

        return opts.Extensions[self._field_ext]

    def field_rules(self, field: descriptor_pb2.FieldDescriptorProto):
        return self._field_rules(field)

    def field_repeated_item_rules(self, field: descriptor_pb2.FieldDescriptorProto):
        rules = self._field_rules(field)
        if rules is None:
            return None
        if _has_field(rules, 'repeated') and _has_field(rules.repeated, 'items'):
            return rules.repeated.items
        return None

    def field_map_key_rules(self, field: descriptor_pb2.FieldDescriptorProto):
        rules = self._field_rules(field)
        if rules is None:
            return None
        if _has_field(rules, 'map') and _has_field(rules.map, 'keys'):
            return rules.map.keys
        return None

    def field_map_value_rules(self, field: descriptor_pb2.FieldDescriptorProto):
        rules = self._field_rules(field)
        if rules is None:
            return None
        if _has_field(rules, 'map') and _has_field(rules.map, 'values'):
            return rules.map.values
        return None

    def field_required(self, field: descriptor_pb2.FieldDescriptorProto):
        rules = self._field_rules(field)
        if rules is None:
            return False

        return bool(rules.required)

    def field_repeated_min_items(
        self, field: descriptor_pb2.FieldDescriptorProto
    ):
        rules = self._field_rules(field)
        if rules is None:
            return None
        if _has_field(rules, 'repeated'):
            return int(rules.repeated.min_items)
        return None

    def field_map_min_pairs(
        self, field: descriptor_pb2.FieldDescriptorProto
    ):
        rules = self._field_rules(field)
        if rules is None:
            return None
        if _has_field(rules, 'map'):
            return int(rules.map.min_pairs)
        return None

    def oneof_required(self, oneof: descriptor_pb2.OneofDescriptorProto):
        if self._oneof_ext is None or self._oneof_options_cls is None:
            return False

        opts = self._oneof_options_cls()
        opts.ParseFromString(oneof.options.SerializeToString())

        # Extensions show up as unknown fields unless the pool knows them.
        if self._oneof_ext not in opts.Extensions:
            return False

        rules = opts.Extensions[self._oneof_ext]
        return bool(rules.required)


class _PyiWriter:
    def __init__(
        self,
        *,
        file_proto: descriptor_pb2.FileDescriptorProto,
        request: plugin_pb2.CodeGeneratorRequest,
        symbols: dict[str, _Symbol],
        protovalidate: _Protovalidate,
    ):
        self._file = file_proto
        self._symbols = symbols
        self._protovalidate = protovalidate

        self._buf = StringIO()
        self._imports: dict[str, str] = {}
        self._map_entry_cache: dict[str, descriptor_pb2.DescriptorProto | None] = {}
        self._enum_meta = _build_enum_meta_table(request.proto_file)
        self._module_by_file = {
            f.name: _proto_to_module(f.name, suffix='_pb2') for f in request.proto_file
        }
        self._types_module_by_file = {
            f.name: _proto_to_module(f.name, suffix='_types')
            for f in request.proto_file
        }
        self._file_enums = tuple(
            _iter_file_enums(file_proto=file_proto, symbols=symbols)
        )
        self._needs_repeated_composite: bool = False
        self._needs_repeated_scalar: bool = False
        self._needs_repeated_enum: bool = False
        self._needs_message_map: bool = False

    def build(self):
        self._collect_imports()
        self._collect_wkt_imports()
        self._emit_header()
        self._emit_imports()
        self._emit_wkt_file_augments()
        self._emit_enums_and_aliases()
        self._emit_messages()
        return self._buf.getvalue()

    def _w(self, text: str = ''):
        self._buf.write(text)
        self._buf.write('\n')

    def _emit_header(self):
        self._w('"""')
        self._w('@generated by scripts/protoc_gen_pyi.py. DO NOT EDIT!')
        self._w('"""')
        self._w()

    def _import_module(self, module: str):
        alias = self._imports.get(module)
        if alias is not None:
            return alias

        base = module.rsplit('.', 1)[-1]
        alias = '_' + base
        if alias in self._imports.values():
            i = 2
            while f'{alias}{i}' in self._imports.values():
                i += 1
            alias = f'{alias}{i}'
        self._imports[module] = alias
        return alias

    def _emit_imports(self):
        self._w('from __future__ import annotations')
        self._w()
        self._w('from collections.abc import *')
        self._w('from typing import *')
        self._w()
        self._w('from google.protobuf.message import Message')
        self._emit_enum_type_imports()
        self._emit_proto_support()
        if self._imports:
            self._w()
            for module, alias in sorted(self._imports.items()):
                self._w(f'import {module} as {alias}')
        self._w()

    def _emit_enum_type_imports(self):
        if not self._file_enums:
            return

        local_types_module = _proto_to_module(self._file.name, suffix='_types').rsplit(
            '.', 1
        )[-1]
        public_alias_names: set[str] = set()
        for enum_def in self._file_enums:
            for suffix in ('', 'Canonical'):
                public_alias_names.add(
                    self._enum_alias_name(enum_def.symbol, suffix=suffix)
                )

        self._w(f'from .{local_types_module} import (')
        for public_name in sorted(public_alias_names):
            self._w(f'    {public_name} as _{public_name},')
        self._w(')')
        self._w()

    def _collect_wkt_imports(self):
        file_aug = _wkt_augments.file_augments(self._file.name)
        if file_aug is not None:
            for t in file_aug.type_aliases.values():
                self._type_to_str(t)

        def walk_message(
            parent_proto: str,
            msg: descriptor_pb2.DescriptorProto,
        ):
            msg_proto = f'{parent_proto}.{msg.name}'
            msg_aug = _wkt_augments.message_augment(msg_proto)
            if msg_aug is not None:
                proto = msg_aug.protocol
                for name in get_protocol_members(proto):
                    attr = getattr(proto, name, None)
                    if isinstance(attr, property):
                        if attr.fget is not None:
                            for t in inspect.get_annotations(
                                attr.fget, eval_str=False
                            ).values():
                                self._type_to_str(t)
                        if attr.fset is not None:
                            for t in inspect.get_annotations(
                                attr.fset, eval_str=False
                            ).values():
                                self._type_to_str(t)
                        continue

                    if not callable(attr):
                        continue
                    overloads = get_overloads(attr) or [attr]
                    for fn in overloads:
                        for t in inspect.get_annotations(fn, eval_str=False).values():
                            self._type_to_str(t)

            for nested in msg.nested_type:
                walk_message(msg_proto, nested)

        package = f'.{self._file.package}' if self._file.package else ''
        for msg in self._file.message_type:
            walk_message(package, msg)

    def _emit_wkt_file_augments(self):
        file_aug = _wkt_augments.file_augments(self._file.name)
        if file_aug is None or not file_aug.type_aliases:
            return

        for name, t in sorted(file_aug.type_aliases.items()):
            self._w(f'{name}: TypeAlias = {self._type_to_str(t)}')
        self._w()

    def _emit_proto_support(self):
        if not (
            self._needs_repeated_composite
            or self._needs_repeated_scalar
            or self._needs_repeated_enum
            or self._needs_message_map
        ):
            return

        self._w()
        self._w("_TMessage = TypeVar('_TMessage', bound=Message)")
        if self._needs_repeated_scalar:
            self._w("_TScalar = TypeVar('_TScalar')")
        if self._needs_repeated_enum:
            self._w("_TEnumParam = TypeVar('_TEnumParam')")
            self._w("_TEnumValue = TypeVar('_TEnumValue', bound=int)")
        if self._needs_message_map:
            self._w("_K = TypeVar('_K', bound=bool | int | str)")

        protocol_blocks = (
            (self._needs_repeated_composite, _REPEATED_COMPOSITE_PROTO_SUPPORT),
            (self._needs_repeated_scalar, _REPEATED_SCALAR_PROTO_SUPPORT),
            (self._needs_repeated_enum, _REPEATED_ENUM_PROTO_SUPPORT),
            (self._needs_message_map, _MESSAGE_MAP_PROTO_SUPPORT),
        )
        for enabled, lines in protocol_blocks:
            if not enabled:
                continue
            self._w()
            for line in lines:
                self._w(line)

    def _qual(self, proto_name: str):
        sym = self._symbols.get(proto_name)
        if sym is None:
            return 'Any'

        if sym.file_name == self._file.name:
            return sym.python_qualname

        module = self._module_by_file.get(sym.file_name)
        if module is None:
            return 'Any'
        alias = self._import_module(module)
        return f'{alias}.{sym.python_qualname}'

    def _type_to_str(self, t: object):
        if t is inspect.Signature.empty:
            return 'Any'
        if isinstance(t, str):
            return t
        if isinstance(t, ForwardRef):
            return t.__forward_arg__
        if isinstance(t, getattr(typing, 'TypeAliasType', ())):
            return self._type_to_str(t.__value__)
        if t is None or t is types.NoneType or t is type(None):
            return 'None'
        if t is Any:
            return 'Any'

        origin = get_origin(t)
        if origin in (types.UnionType, typing.Union):
            return ' | '.join(self._type_to_str(a) for a in get_args(t))
        if origin is typing.Annotated:
            args = get_args(t)
            return self._type_to_str(args[0]) if args else 'Any'
        if origin is typing.Literal:
            lits = ', '.join(repr(a) for a in get_args(t))
            return f'Literal[{lits}]'
        if origin is typing.ClassVar:
            args = get_args(t)
            return self._type_to_str(args[0]) if args else 'Any'

        if origin is not None:
            args = get_args(t)
            base = self._type_to_str(origin)
            if not args:
                return base
            rendered_args = []
            for a in args:
                if a is Ellipsis:
                    rendered_args.append('...')
                else:
                    rendered_args.append(self._type_to_str(a))
            return f'{base}[{", ".join(rendered_args)}]'

        if getattr(t, '__module__', None) == 'builtins':
            return getattr(t, '__qualname__', repr(t))
        if getattr(t, '__module__', None) in ('typing', 'collections.abc'):
            return getattr(t, '__qualname__', repr(t))
        if (
            getattr(t, '__module__', None) == 'google.protobuf.message'
            and getattr(t, '__qualname__', None) == 'Message'
        ):
            return 'Message'

        module = getattr(t, '__module__', None)
        qual = getattr(t, '__qualname__', None)
        if module and qual:
            alias = self._import_module(module)
            return f'{alias}.{qual}'

        return 'Any'

    def _emit_wkt_message_augments(self, *, msg_proto: str, indent: str):
        msg_aug = _wkt_augments.message_augment(msg_proto)
        if msg_aug is None:
            return
        proto = msg_aug.protocol
        members = get_protocol_members(proto)
        ordered_names = [n for n in proto.__dict__ if n in members]

        for name in ordered_names:
            attr = getattr(proto, name, None)
            if isinstance(attr, property):
                if attr.fget is not None:
                    ret = inspect.get_annotations(attr.fget, eval_str=False).get(
                        'return', inspect.Signature.empty
                    )
                    self._w(f'{indent}    @property')
                    self._w(
                        f'{indent}    def {name}(self) -> {self._type_to_str(ret)}: ...'
                    )
                if attr.fset is not None:
                    ann = inspect.get_annotations(attr.fset, eval_str=False)
                    value_t = ann.get('value', inspect.Signature.empty)
                    self._w(f'{indent}    @{name}.setter')
                    self._w(
                        f'{indent}    def {name}(self, value: {self._type_to_str(value_t)}) -> None: ...'
                    )
                continue

            if not callable(attr):
                continue

            overloads = get_overloads(attr)
            fns = list(overloads) if overloads else [attr]

            for fn in fns:
                if overloads:
                    self._w(f'{indent}    @overload')

                sig = inspect.signature(fn)
                ann = inspect.get_annotations(fn, eval_str=False)

                parts: list[str] = []
                for param in sig.parameters.values():
                    if param.name == 'self':
                        continue

                    if param.kind == inspect.Parameter.VAR_POSITIONAL:
                        p = f'*{param.name}: Any'
                    elif param.kind == inspect.Parameter.VAR_KEYWORD:
                        p = f'**{param.name}: Any'
                    else:
                        p = param.name
                        if param.name in ann:
                            p += f': {self._type_to_str(ann[param.name])}'
                        if param.default is not inspect.Parameter.empty:
                            p += ' = ...'

                    parts.append(p)

                ret = ann.get('return', inspect.Signature.empty)
                args_s = ', '.join(['self', *parts])
                self._w(
                    f'{indent}    def {name}({args_s}) -> {self._type_to_str(ret)}: ...'
                )

        # Keep output compact; class separation is handled by callers.

    def _enum_alias_name(self, enum_sym: _Symbol, *, suffix: str):
        prefix = _enum_alias_prefix(enum_sym)
        return f'{prefix}{suffix}' if suffix else prefix

    def _enum_private_alias_name(self, enum_sym: _Symbol, *, suffix: str):
        return f'_{self._enum_alias_name(enum_sym, suffix=suffix)}'

    def _enum_alias_ref(self, enum_sym: _Symbol, suffix: str):
        if enum_sym.file_name == self._file.name:
            return self._enum_private_alias_name(enum_sym, suffix=suffix)
        if suffix == 'Value':
            # Value aliases are intentionally private to stubs.
            return 'int'
        module = self._types_module_by_file.get(enum_sym.file_name)
        if module is None:
            return 'Any'
        alias = self._import_module(module)
        return f'{alias}.{self._enum_alias_name(enum_sym, suffix=suffix)}'

    def _emit_enum_private_aliases(
        self,
        enum_sym: _Symbol,
        enum: descriptor_pb2.EnumDescriptorProto,
    ):
        numbers = list(dict.fromkeys(v.number for v in enum.value))
        number_literals = ', '.join(str(n) for n in numbers) if numbers else '0'
        self._w(
            f'{self._enum_private_alias_name(enum_sym, suffix="Value")}: TypeAlias = Literal[{number_literals}]'
        )

        prefix = _enum_alias_prefix(enum_sym)
        name_ref = self._enum_private_alias_name(enum_sym, suffix='')
        self._w(f'_{prefix}Param: TypeAlias = int | {name_ref}')
        self._w()

    def _enum_param_type(self, enum_sym: _Symbol | None):
        if enum_sym is None:
            return 'int'
        if enum_sym.file_name == self._file.name:
            return self._enum_private_alias_name(enum_sym, suffix='Param')
        return f'int | {self._enum_alias_ref(enum_sym, "")}'

    def _emit_enum_wrapper(
        self,
        enum_sym: _Symbol,
        enum: descriptor_pb2.EnumDescriptorProto,
        *,
        indent: str,
    ):
        wrapper_name = enum_sym.python_qualname.rsplit('.', 1)[-1]
        self._w(f'{indent}class {wrapper_name}:')
        if not enum.value:
            self._w(f'{indent}    ...')
            return

        name_ref = self._enum_alias_ref(enum_sym, '')
        canonical_name_ref = self._enum_alias_ref(enum_sym, 'Canonical')
        value_ref = self._enum_alias_ref(enum_sym, 'Value')

        for v in enum.value:
            _escape_ident(v.name)
            self._w(f'{indent}    {v.name}: Literal[{v.number}]')

        by_number: dict[int, list[str]] = {}
        for v in enum.value:
            by_number.setdefault(v.number, []).append(v.name)

        for number, names in by_number.items():
            canonical_name = names[0]
            self._w(f'{indent}    @overload')
            self._w(f'{indent}    @staticmethod')
            self._w(
                f'{indent}    def Name(number: Literal[{number}]) -> Literal[{canonical_name!r}]: ...'
            )

        self._w(f'{indent}    @overload')
        self._w(f'{indent}    @staticmethod')
        self._w(f'{indent}    def Name(number: int) -> {canonical_name_ref}: ...')

        for v in enum.value:
            self._w(f'{indent}    @overload')
            self._w(f'{indent}    @staticmethod')
            self._w(
                f'{indent}    def Value(name: Literal[{v.name!r}]) -> Literal[{v.number}]: ...'
            )

        self._w(f'{indent}    @overload')
        self._w(f'{indent}    @staticmethod')
        self._w(f'{indent}    def Value(name: {name_ref}) -> {value_ref}: ...')
        self._w()

    def _emit_enums_and_aliases(self):
        # Keep enum `| int` constructor convenience private to stubs while
        # importing canonical enum name/value aliases from `<file>_types.py`.
        for enum_def in self._file_enums:
            self._emit_enum_private_aliases(enum_def.symbol, enum_def.enum)

        # Emit top-level enum wrappers and module-level value constants.
        package = f'.{self._file.package}' if self._file.package else ''
        for enum in self._file.enum_type:
            enum_proto = f'{package}.{enum.name}'
            enum_sym = self._symbols[enum_proto]
            self._emit_enum_wrapper(enum_sym, enum, indent='')
            for v in enum.value:
                self._w(f'{v.name}: Literal[{v.number}]')
            self._w()

    def _collect_imports(self):
        def walk_message(msg: descriptor_pb2.DescriptorProto):
            for field in msg.field:
                map_entry = self._field_map_entry(msg, field)
                is_map = map_entry is not None
                is_repeated = (
                    field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                )

                if (
                    is_repeated
                    and field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                    and not is_map
                ):
                    self._needs_repeated_composite = True

                if is_repeated and is_map and len(map_entry.field) >= 2:
                    val_f = map_entry.field[1]
                    if val_f.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
                        self._needs_message_map = True

                if (
                    is_repeated
                    and field.type != descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                    and not is_map
                ):
                    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
                        self._needs_repeated_enum = True
                    else:
                        self._needs_repeated_scalar = True

                if field.type in (
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
                ):
                    self._qual(field.type_name)
                if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
                    self._import_enum_types_module(field.type_name)
            for nested in msg.nested_type:
                walk_message(nested)

        for msg in self._file.message_type:
            walk_message(msg)

    def _import_enum_types_module(self, proto_name: str):
        enum_sym = self._symbols.get(proto_name)
        if enum_sym is None or enum_sym.file_name == self._file.name:
            return
        module = self._types_module_by_file.get(enum_sym.file_name)
        if module is not None:
            self._import_module(module)

    def _map_entry(
        self,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ):
        type_name = field.type_name
        if type_name in self._map_entry_cache:
            return self._map_entry_cache[type_name]

        entry_name = type_name.rsplit('.', 1)[-1]
        result: descriptor_pb2.DescriptorProto | None = None
        for nested in msg.nested_type:
            if nested.name == entry_name and nested.options.map_entry:
                result = nested
                break
        self._map_entry_cache[type_name] = result
        return result

    def _field_map_entry(
        self,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ):
        if field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            return None
        if field.type != descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
            return None
        return self._map_entry(msg, field)

    def _map_types_from_entry(
        self,
        entry: descriptor_pb2.DescriptorProto | None,
        *,
        key_rules: object | None,
        value_rules: object | None,
    ):
        if entry is None or len(entry.field) < 2:
            return 'Any', 'Any', False, 'Any', 'Any'

        key_f = entry.field[0]
        val_f = entry.field[1]
        key_value_t = self._field_value_type(
            msg=entry, field=key_f, rules_override=key_rules
        )
        key_init_t = self._field_init_type(
            msg=entry, field=key_f, rules_override=key_rules
        )
        value_value_t = self._field_value_type(
            msg=entry, field=val_f, rules_override=value_rules
        )
        value_init_t = self._field_init_type(
            msg=entry, field=val_f, rules_override=value_rules
        )
        return (
            key_value_t,
            value_value_t,
            val_f.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            key_init_t,
            value_init_t,
        )

    def _dedupe_values(self, values: Iterable[object]):
        out: list[object] = []
        for value in values:
            if value in out:
                continue
            out.append(value)
        return tuple(out)

    def _literal_item(self, value: object, *, field_type: int):
        if field_type in (
            descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
            descriptor_pb2.FieldDescriptorProto.TYPE_INT64,
            descriptor_pb2.FieldDescriptorProto.TYPE_UINT64,
            descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
            descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64,
            descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32,
            descriptor_pb2.FieldDescriptorProto.TYPE_UINT32,
            descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32,
            descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64,
            descriptor_pb2.FieldDescriptorProto.TYPE_SINT32,
            descriptor_pb2.FieldDescriptorProto.TYPE_SINT64,
        ):
            if isinstance(value, bool):
                value = int(value)
            if not isinstance(value, int):
                return None
            return repr(value)

        if field_type == descriptor_pb2.FieldDescriptorProto.TYPE_BOOL:
            if not isinstance(value, bool):
                return None
            return repr(value)

        if field_type == descriptor_pb2.FieldDescriptorProto.TYPE_STRING:
            if not isinstance(value, str):
                return None
            return repr(value)

        if field_type == descriptor_pb2.FieldDescriptorProto.TYPE_BYTES:
            if not isinstance(value, (bytes, bytearray)):
                return None
            return repr(bytes(value))

        if field_type in (
            descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE,
            descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT,
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            value_f = float(value)
            if not math.isfinite(value_f):
                return None
            return repr(value_f)

        return None

    def _literal_type(
        self,
        values: Iterable[object],
        *,
        field_type: int,
    ):
        items: list[str] = []
        for value in values:
            literal = self._literal_item(value, field_type=field_type)
            if literal is None:
                return None
            items.append(literal)
        if not items:
            return 'Never'
        return f'Literal[{", ".join(items)}]'

    def _union_type(self, parts: Iterable[str | None]):
        out: list[str] = []
        for part in parts:
            if part is None or part in out:
                continue
            out.append(part)
        if not out:
            return None
        if len(out) == 1:
            return out[0]
        return ' | '.join(out)

    def _enum_name_literal(
        self,
        *,
        enum_meta: _EnumMeta | None,
        numbers: Iterable[int],
    ):
        if enum_meta is None:
            return None
        names: list[str] = []
        for number in numbers:
            for name in enum_meta.names_by_number.get(number, ()):
                if name in names:
                    continue
                names.append(name)
        if not names:
            return None
        return self._literal_type(names, field_type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING)

    def _rules_for_field(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None,
    ):
        if rules_override is not None:
            return rules_override
        return self._protovalidate.field_rules(field)

    def _subset_from_rules(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None,
    ):
        rules = self._rules_for_field(field=field, rules_override=rules_override)
        if rules is None:
            return _ValueSubset()

        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
            if not _has_field(rules, 'enum'):
                return _ValueSubset()

            enum_rules = rules.enum
            in_values: tuple[object, ...] = ()
            if _has_field(enum_rules, 'const'):
                in_values = (int(enum_rules.const),)
            in_values_raw = tuple(getattr(enum_rules, 'in'))
            not_in_values_raw = tuple(enum_rules.not_in)
            if not in_values:
                in_values = self._dedupe_values(int(v) for v in in_values_raw)
            not_in_values = self._dedupe_values(int(v) for v in not_in_values_raw)
            return _ValueSubset(
                in_values=in_values if in_values else None,
                not_in_values=not_in_values,
                defined_only=bool(enum_rules.defined_only),
            )

        branch = _scalar_rule_branch(field.type)
        if branch is None:
            return _ValueSubset()
        if not _has_field(rules, branch):
            return _ValueSubset()

        branch_rules = getattr(rules, branch)
        in_values: tuple[object, ...] = ()
        if _has_field(branch_rules, 'const'):
            in_values = (branch_rules.const,)
        if not in_values:
            in_values = self._dedupe_values(tuple(getattr(branch_rules, 'in')))
        not_in_values = self._dedupe_values(tuple(branch_rules.not_in))
        return _ValueSubset(
            in_values=in_values if in_values else None,
            not_in_values=not_in_values,
        )

    def _enum_getter_init_types(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None,
    ):
        enum_sym = self._symbols.get(field.type_name)
        default_init = self._enum_param_type(enum_sym)

        subset = self._subset_from_rules(field=field, rules_override=rules_override)
        enum_meta = self._enum_meta.get(field.type_name)
        declared_numbers = enum_meta.numbers if enum_meta is not None else ()

        runtime_closed = enum_meta is not None and enum_meta.syntax != 'proto3'
        typing_closed = runtime_closed or subset.defined_only
        subset_active = bool(
            subset.defined_only or subset.in_values is not None or subset.not_in_values
        )

        allowed_numbers: tuple[int, ...] | None = None
        if subset.in_values is not None:
            allowed_numbers = tuple(int(v) for v in subset.in_values)
            if typing_closed and declared_numbers:
                declared_set = set(declared_numbers)
                allowed_numbers = tuple(v for v in allowed_numbers if v in declared_set)
        elif typing_closed:
            allowed_numbers = declared_numbers

        if allowed_numbers is not None and subset.not_in_values:
            banned = set(subset.not_in_values)
            allowed_numbers = tuple(v for v in allowed_numbers if v not in banned)

        allowed_number_literal = (
            self._literal_type(allowed_numbers, field_type=field.type)
            if allowed_numbers is not None
            else None
        )
        allowed_name_literal = (
            self._enum_name_literal(enum_meta=enum_meta, numbers=allowed_numbers)
            if allowed_numbers is not None
            else None
        )
        known_literal = self._literal_type(declared_numbers, field_type=field.type)

        if allowed_number_literal is not None:
            getter = allowed_number_literal if typing_closed else f'{allowed_number_literal} | int'
        elif typing_closed:
            getter = known_literal or 'int'
        else:
            getter = f'{known_literal} | int' if known_literal is not None else 'int'

        init = default_init
        if subset_active and allowed_numbers is not None:
            init = (
                self._union_type((allowed_number_literal, allowed_name_literal))
                or default_init
            )

        return getter, init

    def _scalar_getter_init_types(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None,
    ):
        scalar = _SCALAR_TYPE.get(field.type)
        if scalar is None:
            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
                qual = self._qual(field.type_name)
                return qual, qual
            return 'Any', 'Any'

        subset = self._subset_from_rules(field=field, rules_override=rules_override)
        allowed: tuple[object, ...] | None = subset.in_values

        if (
            allowed is None
            and subset.not_in_values
            and field.type == descriptor_pb2.FieldDescriptorProto.TYPE_BOOL
        ):
            banned = set(subset.not_in_values)
            allowed = tuple(v for v in (False, True) if v not in banned)

        if allowed is not None and subset.not_in_values:
            banned = set(subset.not_in_values)
            allowed = tuple(v for v in allowed if v not in banned)

        allowed_literal = (
            self._literal_type(allowed, field_type=field.type)
            if allowed is not None
            else None
        )
        if allowed_literal is None:
            return scalar, scalar
        return allowed_literal, allowed_literal

    def _singular_field_types(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None,
    ):
        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
            return self._enum_getter_init_types(field=field, rules_override=rules_override)
        return self._scalar_getter_init_types(field=field, rules_override=rules_override)

    def _field_value_type(
        self,
        *,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None = None,
    ):
        if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            map_entry = self._field_map_entry(msg, field)
            if map_entry is not None:
                key_rules = self._protovalidate.field_map_key_rules(field)
                value_rules = self._protovalidate.field_map_value_rules(field)
                k, v, v_is_message, _k_init, _v_init = self._map_types_from_entry(
                    map_entry,
                    key_rules=key_rules,
                    value_rules=value_rules,
                )
                if v_is_message:
                    return f'_MessageMap[{k}, {v}]'
                return f'MutableMapping[{k}, {v}]'
            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
                return f'_RepeatedComposite[{self._qual(field.type_name)}]'
            item_rules = self._protovalidate.field_repeated_item_rules(field)
            value_type, init_type = self._singular_field_types(
                field=field,
                rules_override=item_rules,
            )
            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
                return f'_RepeatedEnum[{init_type}, {value_type}]'
            return f'_RepeatedScalar[{value_type}]'

        value_type, _init_type = self._singular_field_types(
            field=field,
            rules_override=rules_override,
        )
        return value_type

    def _field_init_type(
        self,
        *,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
        rules_override: object | None = None,
    ):
        if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            map_entry = self._field_map_entry(msg, field)
            if map_entry is not None:
                key_rules = self._protovalidate.field_map_key_rules(field)
                value_rules = self._protovalidate.field_map_value_rules(field)
                _k_value, _v_value, _v_is_message, k, v = self._map_types_from_entry(
                    map_entry,
                    key_rules=key_rules,
                    value_rules=value_rules,
                )
                return f'Mapping[{k}, {v}]'
            item_rules = self._protovalidate.field_repeated_item_rules(field)
            _value_type, init_type = self._singular_field_types(
                field=field,
                rules_override=item_rules,
            )
            return f'Iterable[{init_type}]'

        _value_type, init_type = self._singular_field_types(
            field=field,
            rules_override=rules_override,
        )
        return init_type

    def _field_accepts_none(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
    ):
        # Constructor typing policy (DX-oriented):
        # - Repeated/map fields accept `None` at runtime and treat it like empty;
        #   expose that in stubs for convenient conditional argument passing.
        # - For singular scalars without presence, keep strict non-None typing.
        # - For optional/oneof/message fields, allow None to express "unset".
        if self._protovalidate.field_required(field):
            return False
        if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            repeated_min_items = self._protovalidate.field_repeated_min_items(field)
            if repeated_min_items is not None and repeated_min_items > 0:
                return False
            map_min_pairs = self._protovalidate.field_map_min_pairs(field)
            return not (map_min_pairs is not None and map_min_pairs > 0)
        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
            return True
        # In proto2, all singular scalar fields have presence.
        if self._file.syntax != 'proto3':
            return True
        return field.HasField('oneof_index')

    def _emit_messages(self):
        package = f'.{self._file.package}' if self._file.package else ''
        for msg in self._file.message_type:
            self._emit_message(msg=msg, parent_proto=package, indent='')
            self._w()

    def _emit_message(
        self,
        *,
        msg: descriptor_pb2.DescriptorProto,
        parent_proto: str,
        indent: str,
    ):
        msg_proto = f'{parent_proto}.{msg.name}'
        msg_sym = self._symbols[msg_proto]
        name = msg_sym.python_qualname.rsplit('.', 1)[-1]
        self._w(f'{indent}class {name}(Message):')

        if msg.enum_type:
            for enum in msg.enum_type:
                enum_proto = f'{msg_proto}.{enum.name}'
                enum_sym = self._symbols[enum_proto]
                self._emit_enum_wrapper(enum_sym, enum, indent=indent + '    ')

        for nested in msg.nested_type:
            if nested.options.map_entry:
                continue
            self._emit_message(
                msg=nested, parent_proto=msg_proto, indent=indent + '    '
            )

        if not msg.field:
            self._w(f'{indent}    ...')
            return

        # Field number constants
        for field in msg.field:
            const = f'{field.name.upper()}_FIELD_NUMBER'
            self._w(f'{indent}    {const}: int')

        self._w()

        # Field accessors
        for field in msg.field:
            py_name = _escape_field_ident(field.name)
            if py_name is None:
                continue

            if (
                field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                or field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
            ):
                t = self._field_value_type(msg=msg, field=field)
                self._w(f'{indent}    @property')
                self._w(f'{indent}    def {py_name}(self) -> {t}: ...')
                continue

            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
                t = self._field_value_type(msg=msg, field=field)
                init_t = self._field_init_type(msg=msg, field=field)
                self._w(f'{indent}    @property')
                self._w(f'{indent}    def {py_name}(self) -> {t}: ...')
                self._w(f'{indent}    @{py_name}.setter')
                self._w(
                    f'{indent}    def {py_name}(self, value: {init_t}) -> None: ...'
                )
                continue

            t = self._field_value_type(msg=msg, field=field)
            self._w(f'{indent}    {py_name}: {t}')

        self._w()

        keyword_init: dict[str, str] = {}
        for field in msg.field:
            if not keyword.iskeyword(field.name):
                continue
            base = self._field_init_type(msg=msg, field=field)
            if self._field_accepts_none(field=field):
                base = f'{base} | None'
            keyword_init[field.name] = base

        if keyword_init:
            items = ', '.join(f'{k!r}: {v}' for k, v in keyword_init.items())
            self._w(
                f"{indent}    _InitKwargs = TypedDict('_InitKwargs', {{{items}}}, total=False)"
            )
            self._w()

        # __init__
        self._w(f'{indent}    def __init__(')
        self._w(f'{indent}        self,')
        self._w(f'{indent}        *,')
        for field in msg.field:
            py_name = _escape_field_ident(field.name)
            if py_name is None:
                continue
            base = self._field_init_type(msg=msg, field=field)
            if self._field_accepts_none(field=field):
                base = f'{base} | None'
            self._w(f'{indent}        {py_name}: {base} = ...,')
        if keyword_init:
            self._w(f'{indent}        **kwargs: Unpack[_InitKwargs],')
        self._w(f'{indent}    ) -> None: ...')
        self._w()

        # HasField/ClearField/WhichOneof
        field_names = {f.name for f in msg.field}
        oneof_names = {o.name for o in msg.oneof_decl}

        # `FileDescriptorProto.syntax` is omitted for proto2 (default).
        if self._file.syntax != 'proto3':
            present_field_names = {
                f.name
                for f in msg.field
                if f.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
            }
        else:
            present_field_names = {
                f.name
                for f in msg.field
                if f.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                and (
                    f.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                    or f.HasField('oneof_index')
                )
            }

        has_names = sorted(oneof_names | present_field_names)
        clear_names = sorted(oneof_names | field_names)

        clear_lits = ', '.join([
            *(repr(n) for n in clear_names),
            *(repr(n.encode()) for n in clear_names),
        ])
        self._w(f'{indent}    @override')
        self._w(
            f'{indent}    def ClearField(self, field_name: Literal[{clear_lits}]) -> None: ...'
        )

        if has_names:
            has_lits = ', '.join([
                *(repr(n) for n in has_names),
                *(repr(n.encode()) for n in has_names),
            ])
            self._w(f'{indent}    @override')
            self._w(
                f'{indent}    def HasField(self, field_name: Literal[{has_lits}]) -> bool: ...'
            )

        if msg.oneof_decl:
            oneof_items: list[tuple[str, list[str], bool]] = []
            for oneof_index, oneof in enumerate(msg.oneof_decl):
                members = [
                    f.name
                    for f in msg.field
                    if f.HasField('oneof_index') and f.oneof_index == oneof_index
                ]
                if not members:
                    continue

                is_required = self._protovalidate.oneof_required(oneof)
                oneof_items.append((oneof.name, members, is_required))

            if len(oneof_items) == 1:
                name, members, is_required = oneof_items[0]
                member_lits = ', '.join(repr(m) for m in members)
                ret = f'Literal[{member_lits}]'
                if not is_required:
                    ret = f'{ret} | None'
                self._w(f'{indent}    @override')
                self._w(
                    f'{indent}    def WhichOneof(self, oneof_group: Literal[{name!r}, {name.encode()!r}]) -> {ret}: ...'
                )
            elif oneof_items:
                all_members: set[str] = set()
                any_optional_oneof = False
                oneof_group_lits: list[str] = []

                for name, members, is_required in oneof_items:
                    any_optional_oneof |= not is_required
                    all_members.update(members)
                    oneof_group_lits.extend([repr(name), repr(name.encode())])

                    member_lits = ', '.join(repr(m) for m in members)
                    member_ret = f'Literal[{member_lits}]'
                    if not is_required:
                        member_ret = f'{member_ret} | None'
                    self._w(f'{indent}    @overload')
                    self._w(
                        f'{indent}    def WhichOneof(self, oneof_group: Literal[{name!r}, {name.encode()!r}]) -> {member_ret}: ...'
                    )

                # Fallback signature for dynamic (but still typo-protected) oneof
                # group names. Keep it less precise than the overloads, but do not
                # accept arbitrary `str | bytes`.
                group_lits = ', '.join(oneof_group_lits)
                member_lits = ', '.join(repr(m) for m in sorted(all_members))
                ret = f'Literal[{member_lits}]'
                if any_optional_oneof:
                    ret = f'{ret} | None'
                self._w(f'{indent}    @override')
                self._w(
                    f'{indent}    def WhichOneof(self, oneof_group: Literal[{group_lits}]) -> {ret}: ...'
                )

        self._emit_wkt_message_augments(msg_proto=msg_proto, indent=indent)


class _TypesWriter:
    def __init__(
        self,
        *,
        file_proto: descriptor_pb2.FileDescriptorProto,
        symbols: dict[str, _Symbol],
    ):
        self._file = file_proto
        self._file_enums = tuple(
            _iter_file_enums(file_proto=file_proto, symbols=symbols)
        )
        self._buf = StringIO()

    def build(self):
        self._emit_header()
        self._emit_imports()
        self._emit_enums()
        return self._buf.getvalue()

    def _w(self, text: str = ''):
        self._buf.write(text)
        self._buf.write('\n')

    def _emit_header(self):
        self._w('"""')
        self._w('@generated by scripts/protoc_gen_pyi.py. DO NOT EDIT!')
        self._w('"""')
        self._w()

    def _emit_imports(self):
        self._w('from __future__ import annotations')
        self._w()
        self._w('from typing import Literal')
        self._w()

    def _emit_enums(self):
        for enum_def in self._file_enums:
            self._emit_enum_aliases(enum_def.symbol, enum_def.enum)

    def _emit_enum_aliases(
        self,
        enum_sym: _Symbol,
        enum: descriptor_pb2.EnumDescriptorProto,
    ):
        prefix = _enum_alias_prefix(enum_sym)
        names = [v.name for v in enum.value]
        name_literals = ', '.join(repr(n) for n in names)

        canonical_names_by_number: dict[int, str] = {}
        for v in enum.value:
            canonical_names_by_number.setdefault(v.number, v.name)
        canonical_name_literals = ', '.join(
            repr(n) for n in canonical_names_by_number.values()
        )

        self._w(f'type {prefix} = Literal[{name_literals}]')
        if len(canonical_names_by_number) == len(names):
            self._w(f'type {prefix}Canonical = {prefix}')
        else:
            self._w(f'type {prefix}Canonical = Literal[{canonical_name_literals}]')
        self._w()


def _parse_parameters(parameter: str):
    result: dict[str, str] = {}
    if not parameter:
        return result
    for part in filter(None, parameter.split(',')):
        key, has_value, value = part.partition('=')
        result[key.strip()] = value.strip() if has_value else ''
    return result


def main():
    request = plugin_pb2.CodeGeneratorRequest()
    request.ParseFromString(sys.stdin.buffer.read())

    params = _parse_parameters(request.parameter)
    paths = params.get('paths', 'source_relative') or 'source_relative'

    symbols = _build_symbol_table(request.proto_file)
    protovalidate = _Protovalidate(request)

    response = plugin_pb2.CodeGeneratorResponse()
    response.supported_features = (
        plugin_pb2.CodeGeneratorResponse.FEATURE_PROTO3_OPTIONAL
    )
    files_by_name = {f.name: f for f in request.proto_file}

    # Buf/protoc don't emit stubs for google.protobuf's generated modules, but
    # our repo (and buf.validate) imports them. Generate stubs for the
    # dependency-closure subset we actually reference, under `typings/`.
    requested = set(request.file_to_generate)
    pending = list(requested)
    closure: set[str] = set(requested)
    while pending:
        name = pending.pop()
        f = files_by_name.get(name)
        if f is None:
            continue
        for dep in f.dependency:
            if dep in closure:
                continue
            closure.add(dep)
            pending.append(dep)

    google_needed = {n for n in closure if n.startswith('google/protobuf/')}
    for name in sorted(requested | google_needed):
        f = files_by_name.get(name)
        if f is None:
            continue

        if _file_has_enums(f):
            types_writer = _TypesWriter(file_proto=f, symbols=symbols)
            out = response.file.add()
            out.name = _proto_to_output_path(name, paths=paths, suffix='_types.py')
            out.content = types_writer.build()

        writer = _PyiWriter(
            file_proto=f,
            request=request,
            symbols=symbols,
            protovalidate=protovalidate,
        )
        out = response.file.add()
        out.name = _proto_to_output_path(name, paths=paths, suffix='_pb2.pyi')
        out.content = writer.build()

    sys.stdout.buffer.write(response.SerializeToString())


if __name__ == '__main__':
    main()
