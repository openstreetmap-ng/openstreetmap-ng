"""Actual-method probe; DB, SQL, auth and bootstrap are explicit boundaries."""

# ruff: noqa: PT009, PT027
import ast
import sys
import unittest
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BASE = None
if '--baseline' in sys.argv:
    i = sys.argv.index('--baseline')
    BASE = Path(sys.argv[i + 1])
    del sys.argv[i : i + 2]
ENV = {'NoteId': int, 'Note': dict, 'NoteComment': dict}


def load(path, names, class_name=None, root=ROOT):
    body = ast.parse((root / path).read_text(encoding='utf-8')).body
    if class_name:
        body = next(
            n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name
        ).body
    nodes = [
        n
        for n in body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names
    ]
    for n in nodes:
        n.decorator_list = []
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module='__future__', names=[ast.alias(name='annotations')], level=0
            ),
            *nodes,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(root / path), 'exec'), ENV)  # noqa: S102 - trusted local source


load(
    'app/services/changeset_notes.py',
    {'changeset_note_comments', 'close_changeset_notes', 'notify_changeset_notes'},
)
load('app/services/changeset_service.py', {'close'}, 'ChangesetService', BASE or ROOT)
load('app/services/changeset_service.py', {'_close_inactive'}, root=BASE or ROOT)
load(
    'app/services/optimistic_diff/__init__.py', {'run'}, 'OptimisticDiff', BASE or ROOT
)


class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = object()
        self.events = []
        self.store = {1: {'id': 1}, 2: {'id': 2}}
        self.tags = {'closes:note': '1;2', 'comment': 'done'}
        self.inject_failure = False

        @asynccontextmanager
        async def db(write):
            self.assertTrue(write)
            snapshot = deepcopy(self.store)
            try:
                yield self.conn
            except Exception:
                self.store = snapshot
                self.events.append('rollback')
                raise
            else:
                self.events.append('commit')

        async def fetchone(_type, query, *, conn):
            self.assertIs(conn, self.conn)
            note = self.store.get(query.interpolations[0].value)
            return (
                dict(note)
                if note and not note.get('closed_at') and not note.get('hidden_at')
                else None
            )

        async def insert(table, values, *, conn, **_kw):
            self.assertIs(conn, self.conn)
            if table == 'note_comment':
                if self.inject_failure and values['note_id'] == 2:
                    raise RuntimeError('second note')
                self.events.append(('comment', values.copy()))
                return 123, 456
            self.events.append(('subscription', values.copy()))

        async def update(table, values, *, conn=None, **kw):
            if not BASE:
                self.assertIs(conn, self.conn)
            if table == 'note':
                self.store[kw['where']['id']].update(values)

        async def noop(*_args, **_kw):
            return None

        async def fetchrow(*_args, **_kw):
            return (9, None) if BASE else (9, None, self.tags)

        async def fetchrows(*_args, **_kw):
            return [(9, self.tags)]

        async def user(_id):
            return {'id': 9, 'display_name': 'owner'}

        async def notify(note, comment):
            self.assertEqual(self.events[-1], 'commit')
            self.assertEqual(comment['user_id'], 9)
            self.assertEqual(comment['user']['display_name'], 'owner')
            self.assertEqual(self.store[note['id']]['closed_at'], 456)

        ENV.update(
            db=db,
            db_fetchone=fetchone,
            db_insert=insert,
            db_update=update,
            audit=noop,
            db_fetchrow=fetchrow,
            db_fetchrows=fetchrows,
            auth_user=lambda **_kw: {'id': 9},
            UserQuery=SimpleNamespace(find_by_id=user),
            NoteService=SimpleNamespace(notify_activity=notify),
            CHANGESET_IDLE_TIMEOUT=1,
            CHANGESET_OPEN_TIMEOUT=2,
            logging=SimpleNamespace(debug=lambda *_args: None),
        )

        tags = self.tags

        class Prep:
            def __init__(self, conn, elements):
                self.conn = conn
                self.apply_elements = elements
                self.changeset = {
                    'user_id': 9,
                    'tags': tags,
                    'size_limit_reached': True,
                }

            async def prepare(self):
                return None

        ENV.update(
            OptimisticDiffPrepare=Prep,
            OptimisticDiffApply=SimpleNamespace(apply=noop),
            monotonic=lambda: 0,
            OptimisticDiffError=RuntimeError,
            OperationalError=OSError,
        )

    def test_parser_ids_and_defaults(self):
        self.assertEqual(
            ENV['changeset_note_comments']({
                'closes:note': '1;01;0;-1;bad;9223372036854775808',
                'comment': 'default',
            }),
            {1: 'default'},
        )

    def test_parser_overrides_and_empty(self):
        self.assertEqual(
            ENV['changeset_note_comments']({
                'closes:note': '1;2',
                'comment': 'default',
                'closes:note:comment': 'global',
                'closes:note:1:comment': '',
            }),
            {1: '', 2: 'global'},
        )

    async def test_manual_real_method_wiring(self):
        await ENV['close'](17)
        self.assertEqual(self.store[1].get('closed_at'), 456)
        self.assertEqual(self.store[2].get('closed_at'), 456)

    async def test_inactive_real_method_wiring(self):
        await ENV['_close_inactive']()
        self.assertEqual(self.store[1].get('closed_at'), 456)

    async def test_closed_hidden_missing_skipped(self):
        self.store[1]['closed_at'] = 456
        self.store[2]['hidden_at'] = 456
        self.assertEqual(
            await ENV['close_changeset_notes'](self.conn, 9, {'closes:note': '1;2;3'}),
            [],
        )

    async def test_atomic_failure_no_notification(self):
        self.inject_failure = True
        with self.assertRaisesRegex(RuntimeError, 'second note'):
            await ENV['close'](17)
        self.assertNotIn('closed_at', self.store[1])
        self.assertEqual(self.events[-1], 'rollback')

    async def test_no_actor_or_tags_no_mutation(self):
        self.assertEqual(
            await ENV['close_changeset_notes'](self.conn, None, self.tags), []
        )
        self.assertEqual(await ENV['close_changeset_notes'](self.conn, 9, {}), [])
        self.assertEqual(self.events, [])

    async def test_size_limit_actual_run(self):
        await ENV['run']([{'node': 1}])
        self.assertEqual(self.store[1].get('closed_at'), 456)


if __name__ == '__main__':
    unittest.main(verbosity=2)
