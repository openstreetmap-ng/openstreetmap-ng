"""Validate the actual Buf descriptor and history handler without database bootstrap."""

import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

import cython
import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from protovalidate import ValidationError, Validator

ROOT = Path(__file__).resolve().parents[3]
pool = descriptor_pool.Default()
descriptors = descriptor_pb2.FileDescriptorSet.FromString(
    Path(os.environ['HISTORY_DESCRIPTORS']).read_bytes()
)
pending = list(descriptors.file)
while pending:
    progress = False
    for file in pending[:]:
        try:
            pool.FindFileByName(file.name)
        except KeyError:
            try:
                pool.Add(file)
            except TypeError:
                continue
        pending.remove(file)
        progress = True
    if not progress:
        raise RuntimeError(f'Unresolved descriptors: {[file.name for file in pending]}')

Request = message_factory.GetMessageClass(
    pool.FindMessageTypeByName('element.GetHistoryRequest')
)
Response = message_factory.GetMessageClass(
    pool.FindMessageTypeByName('element.GetHistoryResponse')
)
State = message_factory.GetMessageClass(
    pool.FindMessageTypeByName('StandardPaginationState')
)
validator = Validator()


def config_default():
    tree = ast.parse((ROOT / 'app/config.py').read_text(encoding='utf-8'))
    return next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == 'ELEMENT_HISTORY_PAGE_SIZE'
            for target in node.targets
        )
    )


def load_functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name in names
    ]
    assert {node.name for node in nodes} == set(names)
    for node in nodes:
        node.decorator_list = []
    # Execute only the named checkout functions, avoiding native/database bootstrap.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), namespace)  # noqa: S102


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    def test_wire_default_roundtrip_and_validation(self):
        old_client = Request(element={'type': 0, 'id': 1})
        parsed = Request.FromString(old_client.SerializeToString())
        assert parsed.limit == 0
        validator.validate(parsed)
        for limit in (1, 10, 25, 50, 100):
            request = Request(element={'type': 0, 'id': 1}, limit=limit)
            validator.validate(request)
            assert Request.FromString(request.SerializeToString()).limit == limit
        for limit in (101, 1000):
            with pytest.raises(ValidationError):
                validator.validate(Request(element={'type': 0, 'id': 1}, limit=limit))

    async def test_real_handler_and_page_totals(self):
        for requested in (0, 1, 10, 25, 50, 100):
            with self.subTest(limit=requested):
                calls = []

                async def paginate(*args, calls=calls, **kwargs):
                    calls.append(kwargs)
                    state = State(snapshot_max_id=123, page_size=kwargs['page_size'])
                    state.u64.snapshot = 42
                    return [], state

                namespace = {
                    'cython': cython,
                    'ELEMENT_HISTORY_PAGE_SIZE': config_default(),
                    'ElementType': EnumTypeWrapper(
                        pool.FindEnumTypeByName('ElementType')
                    ),
                    'ElementId': int,
                    'SequenceId': int,
                    'typed_element_id': lambda kind, id: (kind, id),
                    'Element': object,
                    'SQL': str,
                    'Identifier': str,
                    'sp_paginate_query': paginate,
                    'GetHistoryRequest': Request,
                    'GetHistoryResponse': Response,
                    'RequestContext': object,
                    'raise_for': SimpleNamespace(),
                }
                load_functions(
                    'app/lib/standard/pagination.py',
                    ('sp_num_pages', '_ceil_div'),
                    namespace,
                )
                load_functions(
                    os.environ.get('HISTORY_HANDLER_SOURCE', 'app/rpc/element.py'),
                    ('get_history',),
                    namespace,
                )
                request = Request(element={'type': 0, 'id': 1}, limit=requested)
                response = await namespace['get_history'](None, request, None)
                size = requested or config_default()
                assert calls[0]['page_size'] == size
                assert calls[0]['order_dir'] == 'desc'
                assert response.state.page_size == size
                assert response.state.known_total.num_items == 123
                assert response.state.known_total.num_pages == (123 + size - 1) // size


if __name__ == '__main__':
    unittest.main()
