from __future__ import annotations

import inspect
import keyword
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

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.compiler import plugin_pb2

try:
    import protoc_gen_pyi_wkt_augments as _wkt_augments
except Exception:
    _wkt_augments = None

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


def _proto_to_python_module(proto_path: str) -> str:
    # protoc's python generator derives module name from proto file path.
    # Example: app/models/proto/shared.proto -> app.models.proto.shared_pb2
    if not proto_path.endswith('.proto'):
        return proto_path.replace('/', '.')
    return proto_path[:-6].replace('/', '.') + '_pb2'


def _proto_to_pyi_path(proto_path: str, *, paths: str) -> str:
    # We only support source-relative output paths.
    if paths != 'source_relative':
        raise ValueError(f'Unsupported paths mode: {paths!r}')
    if not proto_path.endswith('.proto'):
        raise ValueError(f'Unexpected proto path (expected .proto): {proto_path!r}')
    pyi = proto_path[:-6] + '_pb2.pyi'

    # google.protobuf's generated modules live in site-packages, but the
    # protobuf package doesn't ship `.pyi` files for them. Put stubs under
    # `typings/` so Pyright can pick them up without affecting runtime imports.
    if proto_path.startswith('google/protobuf/'):
        return f'typings/{pyi}'

    return pyi


def _escape_ident(name: str) -> str:
    if keyword.iskeyword(name):
        raise ValueError(
            f'Cannot generate stubs for Python keyword identifier: {name!r}. '
            'Rename it in the .proto (protobuf Python exposes keyword-named '
            'fields via getattr only, which is not representable in .pyi).'
        )
    return name


def _escape_field_ident(name: str) -> str | None:
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
    kind: str  # "message" | "enum"


def _build_symbol_table(
    protos: Iterable[descriptor_pb2.FileDescriptorProto],
) -> dict[str, _Symbol]:
    out: dict[str, _Symbol] = {}

    def add_enum(
        *,
        file_name: str,
        parent_proto: str,
        parent_py: str,
        enum: descriptor_pb2.EnumDescriptorProto,
    ) -> None:
        proto_name = f'{parent_proto}.{enum.name}'
        python_qualname = (
            f'{parent_py}.{enum.name}' if parent_py else _escape_ident(enum.name)
        )
        out[proto_name] = _Symbol(
            proto_name=proto_name,
            file_name=file_name,
            python_qualname=python_qualname,
            kind='enum',
        )

    def add_message(
        *,
        file_name: str,
        parent_proto: str,
        parent_py: str,
        msg: descriptor_pb2.DescriptorProto,
    ) -> None:
        proto_name = f'{parent_proto}.{msg.name}'
        python_qualname = (
            f'{parent_py}.{msg.name}' if parent_py else _escape_ident(msg.name)
        )
        out[proto_name] = _Symbol(
            proto_name=proto_name,
            file_name=file_name,
            python_qualname=python_qualname,
            kind='message',
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


class _Protovalidate:
    def __init__(self, request: plugin_pb2.CodeGeneratorRequest) -> None:
        pool = descriptor_pool.DescriptorPool()

        pending = list(request.proto_file)
        while pending:
            next_pending: list[descriptor_pb2.FileDescriptorProto] = []
            progressed = False
            for f in pending:
                try:
                    pool.Add(f)
                except Exception:
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

    def field_required(self, field: descriptor_pb2.FieldDescriptorProto) -> bool:
        if self._field_ext is None or self._field_options_cls is None:
            return False

        opts = self._field_options_cls()
        opts.ParseFromString(field.options.SerializeToString())

        # Extensions show up as unknown fields unless the pool knows them.
        if self._field_ext not in opts.Extensions:
            return False

        rules = opts.Extensions[self._field_ext]
        return bool(getattr(rules, 'required', False))

    def oneof_required(self, oneof: descriptor_pb2.OneofDescriptorProto) -> bool:
        if self._oneof_ext is None or self._oneof_options_cls is None:
            return False

        opts = self._oneof_options_cls()
        opts.ParseFromString(oneof.options.SerializeToString())

        # Extensions show up as unknown fields unless the pool knows them.
        if self._oneof_ext not in opts.Extensions:
            return False

        rules = opts.Extensions[self._oneof_ext]
        return bool(getattr(rules, 'required', False))


class _PyiWriter:
    def __init__(
        self,
        *,
        file_proto: descriptor_pb2.FileDescriptorProto,
        request: plugin_pb2.CodeGeneratorRequest,
        symbols: dict[str, _Symbol],
        protovalidate: _Protovalidate,
        paths: str,
    ) -> None:
        self._file = file_proto
        self._request = request
        self._symbols = symbols
        self._protovalidate = protovalidate
        self._paths = paths

        self._buf = StringIO()
        self._imports: dict[str, str] = {}
        self._module_by_file = {
            f.name: _proto_to_python_module(f.name) for f in request.proto_file
        }
        self._needs_repeated_composite: bool = False
        self._needs_message_map: bool = False

    def build(self) -> str:
        self._collect_imports()
        self._collect_wkt_imports()
        self._emit_header()
        self._emit_imports()
        self._emit_wkt_file_augments()
        self._emit_enums_and_aliases()
        self._emit_messages()
        return self._buf.getvalue()

    def _w(self, text: str = '') -> None:
        self._buf.write(text)
        self._buf.write('\n')

    def _emit_header(self) -> None:
        self._w('"""')
        self._w('@generated by scripts/protoc_gen_pyi.py. DO NOT EDIT!')
        self._w('"""')
        self._w()

    def _import_module(self, module: str) -> str:
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

    def _emit_imports(self) -> None:
        self._w('from __future__ import annotations')
        self._w()
        self._w('from collections.abc import *')
        self._w('from typing import *')
        self._w()
        self._w('from google.protobuf.message import Message')
        self._emit_proto_support()
        if self._imports:
            self._w()
            for module, alias in sorted(self._imports.items()):
                self._w(f'import {module} as {alias}')
        self._w()

    def _collect_wkt_imports(self) -> None:
        if _wkt_augments is None:
            return

        file_aug = _wkt_augments.file_augments(self._file.name)
        if file_aug is not None:
            for t in file_aug.type_aliases.values():
                self._type_to_str(t)

        def walk_message(
            parent_proto: str,
            msg: descriptor_pb2.DescriptorProto,
        ) -> None:
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

    def _emit_wkt_file_augments(self) -> None:
        if _wkt_augments is None:
            return
        file_aug = _wkt_augments.file_augments(self._file.name)
        if file_aug is None or not file_aug.type_aliases:
            return

        for name, t in sorted(file_aug.type_aliases.items()):
            self._w(f'{name}: TypeAlias = {self._type_to_str(t)}')
        self._w()

    def _emit_proto_support(self) -> None:
        if not (self._needs_repeated_composite or self._needs_message_map):
            return

        self._w()
        self._w("_TMessage = TypeVar('_TMessage', bound=Message)")
        if self._needs_message_map:
            self._w("_K = TypeVar('_K', bound=bool | int | str)")

        if self._needs_repeated_composite:
            self._w()
            self._w('class _RepeatedComposite(Protocol[_TMessage]):')
            self._w('    def add(self, **kwargs: Any) -> _TMessage: ...')
            self._w('    def append(self, value: _TMessage) -> None: ...')
            self._w('    def extend(self, values: Iterable[_TMessage]) -> None: ...')
            self._w('    def insert(self, index: int, value: _TMessage) -> None: ...')
            self._w('    def remove(self, value: _TMessage) -> None: ...')
            self._w('    def pop(self, index: int = -1) -> _TMessage: ...')
            self._w('    def clear(self) -> None: ...')
            self._w('    def reverse(self) -> None: ...')
            self._w(
                '    def sort(self, *, key: Callable[[_TMessage], Any] | None = ..., reverse: bool = ...) -> None: ...'
            )
            self._w('    def MergeFrom(self, other: Iterable[_TMessage]) -> None: ...')
            self._w('    def __len__(self) -> int: ...')
            self._w('    def __iter__(self) -> Iterator[_TMessage]: ...')
            self._w('    @overload')
            self._w('    def __getitem__(self, index: int) -> _TMessage: ...')
            self._w('    @overload')
            self._w('    def __getitem__(self, index: slice) -> list[_TMessage]: ...')
            self._w('    @overload')
            self._w('    def __delitem__(self, index: int) -> None: ...')
            self._w('    @overload')
            self._w('    def __delitem__(self, index: slice) -> None: ...')

        if self._needs_message_map:
            self._w()
            self._w(
                'class _MessageMap(Mapping[_K, _TMessage], Protocol[_K, _TMessage]):'
            )
            self._w('    def get_or_create(self, key: _K) -> _TMessage: ...')
            self._w('    def __delitem__(self, key: _K) -> None: ...')
            self._w('    def pop(self, key: _K) -> _TMessage: ...')
            self._w('    def clear(self) -> None: ...')
            self._w(
                '    def MergeFrom(self, other: _MessageMap[_K, _TMessage]) -> None: ...'
            )

    def _qual(self, proto_name: str) -> str:
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

    def _type_to_str(self, t: object) -> str:
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

    def _emit_wkt_message_augments(self, *, msg_proto: str, indent: str) -> None:
        if _wkt_augments is None:
            return
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

    def _enum_alias_prefix(self, enum_sym: _Symbol) -> str:
        return enum_sym.python_qualname.replace('.', '_')

    def _enum_alias_ref(self, enum_sym: _Symbol, suffix: str) -> str:
        name = f'_{self._enum_alias_prefix(enum_sym)}{suffix}'
        if enum_sym.file_name == self._file.name:
            return name
        module = self._module_by_file.get(enum_sym.file_name)
        if module is None:
            return 'Any'
        alias = self._import_module(module)
        return f'{alias}.{name}'

    def _emit_enum_aliases(
        self, enum_sym: _Symbol, enum: descriptor_pb2.EnumDescriptorProto
    ) -> None:
        prefix = self._enum_alias_prefix(enum_sym)
        names = [v.name for v in enum.value]
        name_literals = ', '.join(repr(n) for n in names)

        canonical_names_by_number: dict[int, str] = {}
        for v in enum.value:
            canonical_names_by_number.setdefault(v.number, v.name)
        canonical_name_literals = ', '.join(
            repr(n) for n in canonical_names_by_number.values()
        )

        numbers = list(dict.fromkeys(v.number for v in enum.value))
        number_literals = ', '.join(str(n) for n in numbers) if numbers else '0'
        self._w(f'_{prefix}Name: TypeAlias = Literal[{name_literals}]')
        if len(canonical_names_by_number) == len(names):
            self._w(f'_{prefix}CanonicalName: TypeAlias = _{prefix}Name')
        else:
            self._w(
                f'_{prefix}CanonicalName: TypeAlias = Literal[{canonical_name_literals}]'
            )
        self._w(f'_{prefix}Value: TypeAlias = Literal[{number_literals}]')
        self._w(f'_{prefix}Param: TypeAlias = int | _{prefix}Name')
        self._w()

    def _emit_enum_wrapper(
        self,
        enum_sym: _Symbol,
        enum: descriptor_pb2.EnumDescriptorProto,
        *,
        indent: str,
    ) -> None:
        wrapper_name = enum_sym.python_qualname.rsplit('.', 1)[-1]
        self._w(f'{indent}class {wrapper_name}:')
        if not enum.value:
            self._w(f'{indent}    ...')
            return

        name_ref = self._enum_alias_ref(enum_sym, 'Name')
        canonical_name_ref = self._enum_alias_ref(enum_sym, 'CanonicalName')
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

    def _emit_enums_and_aliases(self) -> None:
        # Emit all enum aliases first (top-level + nested) so they can be referenced
        # from message field annotations without worrying about ordering.
        def walk_message(
            parent_proto: str,
            msg: descriptor_pb2.DescriptorProto,
        ) -> None:
            msg_proto = f'{parent_proto}.{msg.name}'
            for enum in msg.enum_type:
                enum_proto = f'{msg_proto}.{enum.name}'
                enum_sym = self._symbols[enum_proto]
                self._emit_enum_aliases(enum_sym, enum)
            for nested in msg.nested_type:
                walk_message(msg_proto, nested)

        package = f'.{self._file.package}' if self._file.package else ''
        for enum in self._file.enum_type:
            enum_proto = f'{package}.{enum.name}'
            enum_sym = self._symbols[enum_proto]
            self._emit_enum_aliases(enum_sym, enum)
        for msg in self._file.message_type:
            walk_message(package, msg)

        # Emit top-level enum wrappers and module-level value constants.
        for enum in self._file.enum_type:
            enum_proto = f'{package}.{enum.name}'
            enum_sym = self._symbols[enum_proto]
            self._emit_enum_wrapper(enum_sym, enum, indent='')
            for v in enum.value:
                self._w(f'{v.name}: Literal[{v.number}]')
            self._w()

    def _collect_imports(self) -> None:
        def walk_message(msg: descriptor_pb2.DescriptorProto) -> None:
            for field in msg.field:
                if (
                    field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                    and field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                    and not self._field_is_map(msg, field)
                ):
                    self._needs_repeated_composite = True

                if (
                    field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                    and self._field_is_map(msg, field)
                ):
                    entry = self._map_entry(msg, field)
                    if entry is not None and len(entry.field) >= 2:
                        val_f = entry.field[1]
                        if (
                            val_f.type
                            == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                        ):
                            self._needs_message_map = True

                if field.type in (
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
                ):
                    self._qual(field.type_name)
            for nested in msg.nested_type:
                walk_message(nested)

        for msg in self._file.message_type:
            walk_message(msg)

    def _map_entry(
        self,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ) -> descriptor_pb2.DescriptorProto | None:
        entry_name = field.type_name.rsplit('.', 1)[-1]
        for nested in msg.nested_type:
            if nested.name == entry_name and nested.options.map_entry:
                return nested
        return None

    def _field_is_map(
        self,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ) -> bool:
        if field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            return False
        if field.type != descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
            return False
        return self._map_entry(msg, field) is not None

    def _map_types(
        self,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ) -> tuple[str, str, bool]:
        entry = self._map_entry(msg, field)
        if entry is None or len(entry.field) < 2:
            return 'Any', 'Any', False

        key_f = entry.field[0]
        val_f = entry.field[1]
        return (
            self._field_value_type(msg=entry, field=key_f),
            self._field_value_type(msg=entry, field=val_f),
            val_f.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        )

    def _field_value_type(
        self,
        *,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ) -> str:
        if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            if self._field_is_map(msg, field):
                k, v, v_is_message = self._map_types(msg, field)
                if v_is_message:
                    return f'_MessageMap[{k}, {v}]'
                return f'MutableMapping[{k}, {v}]'
            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
                return f'_RepeatedComposite[{self._qual(field.type_name)}]'
            elem = self._field_value_type(
                msg=msg,
                field=descriptor_pb2.FieldDescriptorProto(
                    type=field.type,
                    type_name=field.type_name,
                ),
            )
            return f'MutableSequence[{elem}]'

        if scalar := _SCALAR_TYPE.get(field.type):
            return scalar

        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
            return 'int'

        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
            return self._qual(field.type_name)

        return 'Any'

    def _field_init_type(
        self,
        *,
        msg: descriptor_pb2.DescriptorProto,
        field: descriptor_pb2.FieldDescriptorProto,
    ) -> str:
        if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            if self._field_is_map(msg, field):
                k, v, _v_is_message = self._map_types(msg, field)
                return f'Mapping[{k}, {v}]'
            elem = self._field_value_type(
                msg=msg,
                field=descriptor_pb2.FieldDescriptorProto(
                    type=field.type,
                    type_name=field.type_name,
                ),
            )
            return f'Iterable[{elem}]'

        if scalar := _SCALAR_TYPE.get(field.type):
            return scalar

        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
            enum_sym = self._symbols.get(field.type_name)
            if enum_sym is None:
                return 'int'
            return self._enum_alias_ref(enum_sym, 'Param')

        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
            return self._qual(field.type_name)

        return 'Any'

    def _field_accepts_none(
        self,
        *,
        field: descriptor_pb2.FieldDescriptorProto,
    ) -> bool:
        # Prefer type-safety over protobuf's permissive constructors:
        # - For scalars without presence, passing `None` is rarely intended.
        # - For optional/oneof/message fields, accepting `None` is convenient
        #   to express "unset" when the value is computed conditionally.
        if self._protovalidate.field_required(field):
            return False
        if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
            return False
        if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
            return True
        # In proto2, all singular scalar fields have presence.
        if self._file.syntax != 'proto3':
            return True
        return field.HasField('oneof_index')

    def _emit_messages(self) -> None:
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
    ) -> None:
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


def _parse_parameters(parameter: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if not parameter:
        return result
    for part in parameter.split(','):
        if not part:
            continue
        if '=' in part:
            k, v = part.split('=', 1)
            result[k.strip()] = v.strip()
        else:
            result[part.strip()] = ''
    return result


def main() -> None:
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

        writer = _PyiWriter(
            file_proto=f,
            request=request,
            symbols=symbols,
            protovalidate=protovalidate,
            paths=paths,
        )
        out = response.file.add()
        out.name = _proto_to_pyi_path(name, paths=paths)
        out.content = writer.build()

    sys.stdout.buffer.write(response.SerializeToString())


if __name__ == '__main__':
    main()
