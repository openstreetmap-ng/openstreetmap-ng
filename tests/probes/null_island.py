"""Isolated actual-method probe; not full DB, native speedup or HTTP coverage.

Run: uv run --no-project --python 3.14 --with shapely --with fastapi
     python tests/probes/null_island.py [--source-root BASELINE]
"""

# Standalone unittest avoids the application's autouse DB/bootstrap fixtures.
# ruff: noqa: PT009, PT027, SLF001

import ast
import asyncio
import logging
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from shapely import Point
from starlette import status

ROOT = Path(__file__).resolve().parents[2]
if '--source-root' in sys.argv:
    i = sys.argv.index('--source-root')
    ROOT = Path(sys.argv[i + 1])
    del sys.argv[i : i + 2]


def definitions(path, names, class_name=None):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    body = tree.body
    if class_name:
        body = next(
            n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name
        ).body
    return [
        n
        for n in body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names
    ]


ENV = {
    'APIError': HTTPException,
    'status': status,
    'logging': logging,
    'TaskGroup': asyncio.TaskGroup,
    'defaultdict': defaultdict,
    'element_type': lambda tid: 'way' if tid == 99 else 'node',
    'split_typed_element_id': lambda tid: ('node', tid),
    'ElementStateEntry': SimpleNamespace,
    'auth_user': lambda: ENV['user'],
    'user': {'roles': []},
}


def execute(nodes):
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module='__future__', names=[ast.alias(name='annotations')], level=0
            ),
            *nodes,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(ROOT), 'exec'), ENV)  # noqa: S102 - trusted local source only


execute(definitions('app/models/db/user.py', {'user_is_moderator'}))
error_methods = definitions(
    'app/exceptions/default.py', {'diff_multiple_null_island_nodes'}, 'Exceptions'
)
execute(error_methods)
ENV['raise_for'] = SimpleNamespace(
    diff_multiple_null_island_nodes=lambda: ENV['diff_multiple_null_island_nodes'](None)
)
methods = definitions(
    'app/services/optimistic_diff/prepare.py',
    {'__init__', 'prepare', '_check_null_island_nodes'},
    'OptimisticDiffPrepare',
)
execute([
    ast.ClassDef(name='Prepare', bases=[], keywords=[], body=methods, decorator_list=[])
])
Prepare = ENV['Prepare']


def node(id, x=0, y=0, version=1, visible=True):
    return {
        'typed_id': id,
        'version': version,
        'visible': visible,
        'point': Point(x, y),
        'members': None,
    }


class GuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ENV['user'] = {'roles': []}

    def check(self, elements):
        prep = Prepare(None, [])
        prep.element_state = {
            e['typed_id']: SimpleNamespace(current=e) for e in elements
        }
        prep._check_null_island_nodes()

    def test_two_distinct_nodes_rejected(self):
        with self.assertRaises(HTTPException) as exc:
            self.check([node(-1), node(-2)])
        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn('Null Island', exc.exception.detail)

    def test_single_and_empty_allowed(self):
        self.check([])
        self.check([node(-1)])

    def test_near_origin_and_axes_allowed(self):
        self.check([node(-1), node(-2, x=0.0000001), node(-3, y=-0.0000001)])

    def test_deleted_and_non_nodes_ignored(self):
        self.check([node(-1), node(-2, visible=False), node(99)])

    def test_duplicate_versions_count_once(self):
        self.check([node(-1), node(-1, version=2)])

    def test_final_moved_node_not_counted(self):
        self.check([node(-1), node(-2), node(-2, x=1, version=2)])

    def test_moderator_and_admin_bypass(self):
        for role in ('moderator', 'administrator'):
            ENV['user'] = {'roles': [role]}
            self.check([node(-1), node(-2)])

    def test_other_roles_do_not_bypass(self):
        ENV['user'] = {'roles': ['user']}
        with self.assertRaises(HTTPException):
            self.check([node(-1), node(-2)])

    async def prepare(self, elements):
        prep = Prepare(None, elements)

        async def noop(*args):
            return None

        async def preload():
            prep.changeset = {}

        prep._preload_changeset = preload
        prep._preload_elements_state = noop
        prep._preload_elements_parents = noop
        prep._update_changeset_bounds = noop
        prep._check_members_remote = noop
        prep._push_bbox_info = lambda *_args: None
        prep._check_element_can_delete = lambda *_args: True
        prep._update_changeset_size = lambda **_kw: None
        ENV['ElementQuery'] = SimpleNamespace(
            get_current_sequence_id=lambda: asyncio.sleep(0, result=1)
        )
        ENV['ChangesetBoundsQuery'] = SimpleNamespace(resolve_bounds=noop)
        await prep.prepare()
        return prep

    async def test_actual_prepare_rejects_before_apply(self):
        with self.assertRaises(HTTPException):
            await self.prepare([node(-1), node(-2)])

    async def test_actual_prepare_uses_final_state(self):
        prep = await self.prepare([node(-1), node(-2), node(-2, x=1, version=2)])
        self.assertEqual(len(prep.apply_elements), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
