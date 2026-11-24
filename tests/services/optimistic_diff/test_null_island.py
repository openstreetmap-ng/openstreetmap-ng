"""Exercise full preparation with only query/auth/infrastructure boundaries faked."""

from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest
from shapely import MultiPolygon, Point, box

import app.services.optimistic_diff as diff_module
import app.services.optimistic_diff.apply as apply_module
import app.services.optimistic_diff.prepare as prepare_module
from app.exceptions.api06 import Exceptions06
from app.exceptions.api_error import APIError
from app.exceptions.context import exceptions_context
from app.lib.auth.context import auth_context
from app.services.optimistic_diff import OptimisticDiff
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare
from speedup import typed_element_id

_NULL_ISLAND_DETAIL = 'Multiple nodes at (0, 0) are not allowed in one upload'


def _single_error(exception):
    while isinstance(exception, ExceptionGroup):
        assert len(exception.exceptions) == 1
        exception = exception.exceptions[0]
    assert isinstance(exception, APIError)
    return exception


def _node(id, point=(0, 0), *, version=1, visible=True):
    return {
        'changeset_id': 1,
        'typed_id': typed_element_id('node', id),
        'version': version,
        'visible': visible,
        'tags': {} if visible else None,
        'point': Point(*point) if point is not None else None,
        'members': None,
        'members_roles': None,
    }


def _container(type_, id, members):
    return {
        'changeset_id': 1,
        'typed_id': typed_element_id(type_, id),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': members,
        'members_roles': [''] * len(members) if type_ == 'relation' else None,
    }


@pytest.fixture
def upload(monkeypatch):
    """Fake remote queries and writes; leave every preparation method intact."""
    state = SimpleNamespace(
        user={
            'id': 1,
            'roles': [],
            'email': 'unit@test.invalid',
            'display_name': 'unit',
            'timezone': None,
        },
        changeset={
            'id': 1,
            'user_id': 1,
            'closed_at': None,
            'size': 0,
            'num_create': 0,
            'num_modify': 0,
            'num_delete': 0,
            'union_bounds': None,
        },
        remote={},
        parents={},
        hidden=set(),
        calls=[],
        writes=[],
    )

    async def find_changeset(id, **kwargs):
        state.calls.append('changeset')
        return state.changeset if id == state.changeset['id'] else None

    async def sequence_id():
        state.calls.append('sequence')
        return 10

    async def find_elements(refs, **kwargs):
        state.calls.append('elements')
        return [deepcopy(state.remote[ref]) for ref in set(refs) if ref in state.remote]

    async def parents(refs, *args, **kwargs):
        state.calls.append('parents')
        return {ref: set(state.parents.get(ref, ())) for ref in refs}

    async def resolve_bounds(changesets):
        state.calls.append('resolve_bounds')

    async def hidden_refs(refs, **kwargs):
        state.calls.append('remote_members')
        return set(refs) & state.hidden

    def extend_bounds(old, points):
        state.calls.append('extend_bounds')
        coords = np.array([(point.x, point.y) for point in points])
        return MultiPolygon([box(*coords.min(axis=0), *coords.max(axis=0))])

    async def forbid_write(*args, **kwargs):
        state.writes.append('database/audit')
        raise AssertionError('Rejected upload reached a persistent write boundary')

    class Connection:
        execute = staticmethod(forbid_write)

    state.conn = Connection()

    @asynccontextmanager
    async def db(*args):
        yield state.conn

    monkeypatch.setattr(prepare_module.ChangesetQuery, 'find_by_id', find_changeset)
    monkeypatch.setattr(
        prepare_module.ChangesetBoundsQuery, 'resolve_bounds', resolve_bounds
    )
    monkeypatch.setattr(
        prepare_module.ElementQuery, 'get_current_sequence_id', sequence_id
    )
    monkeypatch.setattr(prepare_module.ElementQuery, 'find_by_refs', find_elements)
    monkeypatch.setattr(prepare_module.ElementQuery, 'map_refs_to_parent_refs', parents)
    monkeypatch.setattr(prepare_module.ElementQuery, 'filter_hidden_refs', hidden_refs)
    monkeypatch.setattr(prepare_module, 'extend_changeset_bounds', extend_bounds)
    monkeypatch.setattr(diff_module, 'db', db)
    monkeypatch.setattr(apply_module, 'audit', forbid_write)
    monkeypatch.setattr(apply_module, 'compressible_geometry', lambda point: point)

    async def prepare(elements):
        prep = OptimisticDiffPrepare(state.conn, elements)
        with auth_context(state.user), exceptions_context(Exceptions06()):
            await prep.prepare()
        return prep

    state.prepare = prepare
    return state


@pytest.mark.parametrize('count', [2, 3])
async def test_rejects_multiple_created_null_island_nodes(upload, count):
    with pytest.raises(APIError) as error:
        await upload.prepare([_node(-id) for id in range(1, count + 1)])
    assert error.value.status_code == 412
    assert error.value.detail == _NULL_ISLAND_DETAIL


@pytest.mark.parametrize('mixed', [False, True])
async def test_rejects_modified_and_mixed_null_island_nodes(upload, mixed):
    upload.remote = {typed_element_id('node', id): _node(id, (id, id)) for id in (1, 2)}
    nodes = [_node(1, version=2), _node(-1) if mixed else _node(2, version=2)]
    with pytest.raises(APIError) as error:
        await upload.prepare(nodes)
    assert error.value.status_code == 412
    assert error.value.detail == _NULL_ISLAND_DETAIL


@pytest.mark.parametrize(
    'points',
    [
        [(0, 0)],
        [(1, 1), (2, 2)],
        [(0, 0), (1e-12, 0)],
        [(0, 0), (0, -1e-12)],
        [(0, 1), (1, 0)],
    ],
    ids=['single-zero', 'no-zero', 'near-longitude', 'near-latitude', 'axes-only'],
)
async def test_accepts_points_outside_exact_multiple_zero_rule(upload, points):
    prep = await upload.prepare([
        _node(-id, point) for id, point in enumerate(points, 1)
    ])
    assert len(prep.apply_elements) == len(points)
    assert prep.changeset['size'] == len(points)


async def test_signed_zero_counts_as_zero(upload):
    with pytest.raises(APIError) as error:
        await upload.prepare([_node(-1), _node(-2, (-0.0, 0.0))])
    assert error.value.detail == _NULL_ISLAND_DETAIL


async def test_counts_final_state_after_node_moves_away(upload):
    prep = await upload.prepare([_node(-1), _node(-2), _node(-2, (1, 1), version=2)])
    assert len(prep.apply_elements) == 3
    assert prep.element_state[typed_element_id('node', -2)].current['point'] == Point(
        1, 1
    )


async def test_counts_final_state_after_node_moves_to_zero(upload):
    with pytest.raises(APIError) as error:
        await upload.prepare([_node(-1), _node(-2, (1, 1)), _node(-2, version=2)])
    assert error.value.detail == _NULL_ISLAND_DETAIL


async def test_multiple_revisions_of_one_node_are_one_distinct_node(upload):
    prep = await upload.prepare([_node(-1, version=version) for version in (1, 2, 3)])
    assert len(prep.apply_elements) == 3
    assert len(prep.element_state) == 1


async def test_final_deletions_do_not_count(upload):
    upload.remote = {typed_element_id('node', id): _node(id) for id in (1, 2)}
    prep = await upload.prepare([
        _node(1, version=2),
        _node(2, None, version=2, visible=False),
    ])
    assert not prep.element_state[typed_element_id('node', 2)].current['visible']
    assert len(prep.apply_elements) == 2


async def test_created_then_deleted_node_does_not_count(upload):
    prep = await upload.prepare([
        _node(-1),
        _node(-2),
        _node(-2, None, version=2, visible=False),
    ])
    assert not prep.element_state[typed_element_id('node', -2)].current['visible']


async def test_skipped_delete_does_not_add_an_unchanged_null_node(upload):
    upload.remote = {typed_element_id('node', id): _node(id) for id in (1, 2)}
    upload.parents[typed_element_id('node', 2)] = {typed_element_id('way', 99)}
    delete = _node(2, None, version=2, visible=False) | {'delete_if_unused': True}
    prep = await upload.prepare([_node(1, version=2), delete])
    assert len(prep.apply_elements) == 1
    assert prep.element_state[typed_element_id('node', 2)].current['version'] == 1


async def test_two_skipped_deletions_of_null_nodes_are_a_successful_noop(upload):
    upload.remote = {typed_element_id('node', id): _node(id) for id in (1, 2)}
    upload.parents = {
        typed_element_id('node', id): {typed_element_id('way', 99)} for id in (1, 2)
    }
    elements = [
        _node(id, None, version=2, visible=False) | {'delete_if_unused': True}
        for id in (1, 2)
    ]
    prep = await upload.prepare(elements)
    assert not prep.apply_elements
    assert all(entry.current['visible'] for entry in prep.element_state.values())


async def test_zero_nodes_in_prior_upload_are_not_counted(upload):
    # The remote store has an unrelated existing null node and an earlier upload
    # contributes to changeset size. This upload contains just one null node.
    upload.remote[typed_element_id('node', 99)] = _node(99)
    upload.changeset['size'] = 1
    prep = await upload.prepare([_node(-1)])
    assert len(prep.element_state) == 1
    assert prep.changeset['size'] == 2


async def test_two_separate_uploads_each_with_one_zero_are_allowed(upload):
    first = await upload.prepare([_node(-1)])
    second = await upload.prepare([_node(-2)])
    assert len(first.element_state) == len(second.element_state) == 1
    assert upload.changeset['size'] == 2


async def test_bbox_only_remote_null_nodes_do_not_count(upload):
    refs = [typed_element_id('node', id) for id in (1, 2)]
    upload.remote = {ref: _node(id) for id, ref in enumerate(refs, 1)}
    prep = await upload.prepare([_container('way', -1, refs)])
    assert len(prep.element_state) == 1
    assert len(prep.apply_elements) == 1
    assert 'elements' in upload.calls


async def test_way_and_relation_are_not_nodes_and_use_real_numpy(upload):
    node = _node(-1)
    ref = node['typed_id']
    prep = await upload.prepare([
        node,
        _container('way', -1, [ref]),
        _container('relation', -1, [ref]),
    ])
    assert len(prep.apply_elements) == 3
    for element in prep.apply_elements[1:]:
        assert isinstance(element['members_arr'], np.ndarray)
        assert element['members_arr'].dtype == np.uint64
        assert element['unassigned_member_indices'] == [0]


async def test_repeated_way_references_do_not_duplicate_node_count(upload):
    node = _node(-1)
    prep = await upload.prepare([node, _container('way', -1, [node['typed_id']] * 3)])
    assert len(prep.element_state) == 2
    assert prep.apply_elements[1]['unassigned_member_indices'] == [0, 1, 2]


@pytest.mark.parametrize(
    'roles', [['moderator'], ['administrator'], ['moderator', 'administrator']]
)
async def test_moderator_and_administrator_bypass_only_null_rule(upload, roles):
    upload.user['roles'] = roles
    prep = await upload.prepare([_node(-1), _node(-2), _node(-3)])
    assert len(prep.apply_elements) == 3
    assert prep.changeset['size'] == 3


@pytest.mark.parametrize('reason', ['owner', 'closed', 'version', 'size', 'member'])
async def test_existing_errors_keep_precedence_over_null_island(upload, reason):
    elements = [_node(-1), _node(-2)]
    if reason == 'owner':
        upload.changeset['user_id'] = 2
        status, detail = 409, "The user doesn't own that changeset"
    elif reason == 'closed':
        upload.changeset['closed_at'] = datetime(2026, 1, 1, tzinfo=UTC)
        status, detail = 409, 'The changeset 1 was closed at'
    elif reason == 'version':
        elements.append(_node(-1, version=3))
        status, detail = 409, 'Version mismatch:'
    elif reason == 'size':
        upload.changeset['size'] = 10_000
        status, detail = 412, 'Changeset size 10002 is too big.'
    else:
        hidden_ref = typed_element_id('node', 99)
        upload.hidden.add(hidden_ref)
        elements.append(_container('way', -1, [hidden_ref]))
        status, detail = 412, 'requires the nodes'

    with pytest.raises((APIError, ExceptionGroup)) as error:
        await upload.prepare(elements)
    exception = _single_error(error.value)
    assert exception.status_code == status
    assert detail in exception.detail
    assert exception.detail != _NULL_ISLAND_DETAIL
    assert not upload.writes


async def test_moderator_still_must_own_changeset(upload):
    upload.user['roles'] = ['moderator']
    upload.changeset['user_id'] = 2
    with pytest.raises(APIError) as error:
        await upload.prepare([_node(-1), _node(-2)])
    assert error.value.status_code == 409
    assert error.value.detail == "The user doesn't own that changeset"


async def test_rejected_upload_never_reaches_apply_writes(upload):
    with (
        auth_context(upload.user),
        exceptions_context(Exceptions06()),
        pytest.raises((APIError, ExceptionGroup)) as error,
    ):
        await OptimisticDiff.run([_node(-1), _node(-2)])
    exception = _single_error(error.value)
    assert exception.status_code == 412
    assert exception.detail == _NULL_ISLAND_DETAIL
    assert not upload.writes
