import logging
from asyncio import TaskGroup
from collections import defaultdict
from dataclasses import dataclass
from typing import Final, Literal

import cython
import numpy as np
from psycopg import AsyncConnection
from shapely import Point, bounds, box

from app.lib.auth_context import auth_user
from app.lib.changeset_bounds import extend_changeset_bounds
from app.lib.exceptions_context import raise_for
from app.models.db.changeset import Changeset, changeset_increase_size
from app.models.db.element import Element, ElementInit
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_NODE_MIN,
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
    ElementType,
    TypedElementId,
)
from app.models.types import SequenceId
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from speedup import element_id, element_type, split_typed_element_id

OSMChangeAction = Literal['create', 'modify', 'delete']


@dataclass(kw_only=True, slots=True)
class ElementStateEntry:
    remote: Final[Element | None]
    current: ElementInit


@dataclass(slots=True)
class OptimisticDiffPrepare:
    conn: AsyncConnection
    """
    Shared connection for the entire operation.
    """

    at_sequence_id: SequenceId
    """
    sequence_id at which the optimistic diff is performed.
    """

    apply_elements: list[ElementInit]
    """
    Processed elements to be applied into the database.
    """

    _elements: list[ElementInit]
    """
    Input elements processed during the preparation step.
    """

    element_state: dict[TypedElementId, ElementStateEntry]
    """
    Local element state, mapping from element ref to remote and local elements.
    """

    _elements_parents_refs: dict[TypedElementId, set[TypedElementId]]
    """
    Local element parents cache, mapping from element ref to the set of parent element refs.
    """

    _elements_check_members_remote: dict[TypedElementId, TypedElementId]
    """
    Mapping from member ref to parent ref, for members to be checked remotely.
    """

    reference_check_element_refs: set[TypedElementId]
    """
    Local reference check state, set of element refs that need to be checked for references after last_sequence_id.
    """

    _reference_override: defaultdict[tuple[TypedElementId, bool], set[TypedElementId]]
    """
    Local reference override, mapping from (element ref, override) tuple to the set of referenced element refs.

    For example, `(way/1, False)` = `{node/1, node/2}` means that way/1 no longer references node/1 and node/2 locally.
    """

    changeset: Changeset
    """
    Local changeset state.
    """

    _bbox_points: list[Point]
    """
    Changeset bounding box collection of points.
    """

    _bbox_refs: set[TypedElementId]
    """
    Changeset bounding box set of element refs.
    """

    def __init__(self, conn: AsyncConnection, elements: list[ElementInit], /):
        self.conn = conn
        self.apply_elements = []
        self._elements = list(map(dict.copy, elements))  # type: ignore
        self.element_state = {}
        self._elements_parents_refs = {}
        self._elements_check_members_remote = {}
        self.reference_check_element_refs = set()
        self._reference_override = defaultdict(set)
        self._bbox_points = []
        self._bbox_refs = set()

    async def prepare(self) -> None:
        await self._preload_changeset()

        # Mark unassigned typed_ids
        for element in self._elements:
            if (tid := element['typed_id']) & (1 << 59):
                element['unassigned_typed_id'] = tid

        self.at_sequence_id = await ElementQuery.get_current_sequence_id()
        logging.debug('Optimistic preparing at sequence_id %d', self.at_sequence_id)

        async with TaskGroup() as tg:
            tg.create_task(self._preload_elements_state())
            tg.create_task(self._preload_elements_parents())
            tg.create_task(ChangesetBoundsQuery.resolve_bounds([self.changeset]))

        # Use local variables for faster access + explicit type hints
        element_state: dict[TypedElementId, ElementStateEntry] = self.element_state
        apply_elements: list[ElementInit] = self.apply_elements
        num_create: cython.size_t = 0
        num_modify: cython.size_t = 0
        num_delete: cython.size_t = 0

        action: OSMChangeAction
        entry: ElementStateEntry | None
        prev: ElementInit | None

        for element in self._elements:
            typed_id = element['typed_id']
            type, id = split_typed_element_id(typed_id)
            version = element['version']

            if version == 1:  # Handle element creation
                action = 'create'
                num_create += 1

                if id >= 0:
                    raise_for.diff_create_bad_id(element)
                assert typed_id not in element_state, (
                    f'Element {typed_id} must not exist in the element state'
                )

                entry = None
                prev = None

            else:  # Handle element modification and deletion
                if element['visible']:
                    action = 'modify'
                    num_modify += 1
                else:
                    action = 'delete'
                    num_delete += 1

                entry = element_state.get(typed_id)
                if entry is None:
                    raise_for.element_not_found(typed_id)

                prev = entry.current
                if prev['version'] + 1 != version:
                    raise_for.element_version_conflict(element, prev['version'])
                if action == 'delete' and not prev['visible']:
                    raise_for.element_already_deleted(typed_id)

            if type != 'node':
                if (members := element['members']) is not None:
                    element['members_arr'] = np.array(members, np.uint64)

                # Update references and check if all newly added members are valid
                added_members_refs = self._update_reference_override(
                    prev, element, typed_id
                )
                if added_members_refs:
                    self._check_members_local(element, added_members_refs)

            # On delete, check if not referenced by other elements
            if action == 'delete' and not self._check_element_can_delete(element):
                logging.debug('Optimistic skipping delete for %s (is used)', typed_id)
                continue

            # Mark unassigned members
            if (members_arr := element.get('members_arr')) is not None:
                indices = np.nonzero(members_arr & (1 << 59))[0]
                if len(indices):
                    element['unassigned_member_indices'] = indices.tolist()

            self._push_bbox_info(prev, element, type)
            apply_elements.append(element)

            # Update the current element state
            if entry is None:
                element_state[typed_id] = ElementStateEntry(
                    remote=None, current=element
                )
            else:
                entry.current = element

        self._update_changeset_size(
            num_create=num_create,
            num_modify=num_modify,
            num_delete=num_delete,
        )

        async with TaskGroup() as tg:
            tg.create_task(self._update_changeset_bounds())
            tg.create_task(self._check_members_remote())

    async def _preload_elements_state(self) -> None:
        """Preload elements state from the database."""
        # Only preload elements that exist in the database
        typed_ids = [
            element['typed_id']
            for element in self._elements
            if 'unassigned_typed_id' not in element
        ]
        num_typed_ids: cython.size_t = len(typed_ids)
        if not num_typed_ids:
            return

        logging.debug('Optimistic preloading %d elements', num_typed_ids)
        elements = await ElementQuery.find_by_refs(
            typed_ids,
            at_sequence_id=self.at_sequence_id,
            limit=num_typed_ids,
        )

        # Check if all elements exist
        if len(elements) != num_typed_ids:
            found_tids = {element['typed_id'] for element in elements}
            missing_tid = next(tid for tid in typed_ids if tid not in found_tids)
            raise_for.element_not_found(missing_tid)

        # Precompute members_arr for reference tracking
        for element in elements:
            if (members := element['members']) is not None:
                element['members_arr'] = np.array(members, np.uint64)

        # Push them to the element state
        self.element_state = {
            element['typed_id']: ElementStateEntry(remote=element, current=element)
            for element in elements
        }

    async def _preload_elements_parents(self) -> None:
        """Preload elements parents from the database."""
        # Only preload elements that exist in the database and will be deleted
        typed_ids = [
            element['typed_id']
            for element in self._elements
            if 'unassigned_typed_id' not in element  #
            and not element['visible']
        ]
        if not typed_ids:
            return

        logging.debug('Optimistic preloading parents for %d elements', len(typed_ids))
        self._elements_parents_refs = await ElementQuery.map_refs_to_parent_refs(
            typed_ids, self.conn, limit=None
        )

    def _check_element_can_delete(self, element: ElementInit) -> bool:
        """Check if the element can be deleted."""
        typed_id = element['typed_id']

        # Check if not referenced by element state
        positive_refs = self._reference_override[typed_id, True]
        if positive_refs:
            if element.get('delete_if_unused'):
                return False
            raise_for.element_in_use(typed_id, list(positive_refs))

        # Check if not referenced by database elements
        # Logical optimization: skip new elements
        if 'unassigned_typed_id' in element:
            return True

        parent_typed_ids = self._elements_parents_refs[typed_id]
        if parent_typed_ids:
            negative_refs = self._reference_override[typed_id, False]
            used_by = parent_typed_ids - negative_refs
            used_by.discard(typed_id)  # Allow self-reference deletion
            if used_by:
                if element.get('delete_if_unused'):
                    return False
                raise_for.element_in_use(typed_id, list(used_by))

        # Mark for reference check during apply
        self.reference_check_element_refs.add(typed_id)
        return True

    def _update_reference_override(
        self,
        prev: ElementInit | None,
        element: ElementInit,
        typed_id: TypedElementId,
    ) -> list[TypedElementId] | None:
        """Update the local reference overrides. Returns the newly added references if any."""
        next_members_arr = element.get('members_arr')
        prev_members_arr = prev.get('members_arr') if prev is not None else None
        next_unique = (
            np.unique(next_members_arr) if next_members_arr is not None else None
        )
        prev_unique = (
            np.unique(prev_members_arr) if prev_members_arr is not None else None
        )
        if next_unique is None and prev_unique is None:
            return None

        if next_unique is not None and prev_unique is not None:
            typed_ids_removed = np.setdiff1d(
                prev_unique, next_unique, assume_unique=True
            )
            typed_ids_added = np.setdiff1d(next_unique, prev_unique, assume_unique=True)
        elif next_unique is not None:
            typed_ids_removed = None
            typed_ids_added = next_unique
        else:
            assert prev_unique is not None
            typed_ids_removed = prev_unique
            typed_ids_added = None

        reference_override = self._reference_override

        # Remove old references
        if typed_ids_removed is not None:
            typed_ids_removed_: list[TypedElementId] = typed_ids_removed.tolist()
            for ref in typed_ids_removed_:
                reference_override[ref, True].discard(typed_id)
                reference_override[ref, False].add(typed_id)

        # Add new references
        if typed_ids_added is not None:
            typed_ids_added_: list[TypedElementId] = typed_ids_added.tolist()
            for ref in typed_ids_added_:
                reference_override[ref, True].add(typed_id)
                reference_override[ref, False].discard(typed_id)
            return typed_ids_added_

        return None

    def _check_members_local(
        self, parent: ElementInit, members: list[TypedElementId]
    ) -> None:
        """
        Check if the members exist and are visible using element state.
        Stores not found member refs for remote check.
        """
        element_state: dict[TypedElementId, ElementStateEntry]
        element_state = self.element_state
        parent_tid = parent['typed_id']
        not_found: list[TypedElementId] = []

        for member in members:
            entry = element_state.get(member)

            if entry is None:
                # Prevent self-reference during creation
                if member == parent_tid:
                    if not parent['visible']:
                        raise_for.element_member_not_found(parent_tid, member)
                    continue

                not_found.append(member)
                continue

            if not entry.current['visible']:
                raise_for.element_member_not_found(parent_tid, member)

        if not_found:
            self._elements_check_members_remote |= dict.fromkeys(not_found, parent_tid)

    def _push_bbox_info(
        self, prev: ElementInit | None, element: ElementInit, element_type: ElementType
    ) -> None:
        """Push bbox info for later processing."""
        if element_type == 'node':
            self._push_bbox_node_info(prev, element)
        elif element_type == 'way':
            self._push_bbox_way_info(prev, element)
        elif element_type == 'relation':
            self._push_bbox_relation_info(prev, element)
        else:
            raise NotImplementedError(f'Unsupported element type {element_type!r}')

    def _push_bbox_node_info(
        self, prev: ElementInit | None, element: ElementInit
    ) -> None:
        """Push bbox info for a node."""
        bbox_points = self._bbox_points

        element_point = element['point']
        if element_point is not None:
            bbox_points.append(element_point)

        prev_point = prev['point'] if prev is not None else None
        if prev_point is not None:
            bbox_points.append(prev_point)

    def _push_bbox_way_info(
        self, prev: ElementInit | None, element: ElementInit
    ) -> None:
        """Push bbox info for a way. Way info contains all nodes."""
        next_members_arr = element.get('members_arr')
        prev_members_arr = prev.get('members_arr') if prev is not None else None
        if next_members_arr is None and prev_members_arr is None:
            return

        if next_members_arr is not None and prev_members_arr is not None:
            typed_ids_arr = np.union1d(next_members_arr, prev_members_arr)
        elif next_members_arr is not None:
            typed_ids_arr = np.unique(next_members_arr)
        else:
            assert prev_members_arr is not None
            typed_ids_arr = np.unique(prev_members_arr)

        typed_ids: list[TypedElementId] = typed_ids_arr.tolist()

        element_state: dict[TypedElementId, ElementStateEntry] = self.element_state
        bbox_points: list[Point] = self._bbox_points
        bbox_refs: set[TypedElementId] = self._bbox_refs

        for typed_id in typed_ids:
            entry = element_state.get(typed_id)
            if entry is None:
                bbox_refs.add(typed_id)
                continue

            point = entry.current['point']
            assert point is not None, f'Node {typed_id} point must be set'
            bbox_points.append(point)

    def _push_bbox_relation_info(
        self,
        prev: ElementInit | None,
        element: ElementInit,
        *,
        TYPED_ELEMENT_ID_RELATION_MIN=TYPED_ELEMENT_ID_RELATION_MIN,
        TYPED_ELEMENT_ID_RELATION_MAX=TYPED_ELEMENT_ID_RELATION_MAX,
    ) -> None:
        """Push bbox info for a relation. Relation info contains either all members or only changed members."""
        next_members_arr = element.get('members_arr')
        prev_members_arr = prev.get('members_arr') if prev is not None else None
        if next_members_arr is None and prev_members_arr is None:
            return

        if next_members_arr is not None and prev_members_arr is not None:
            typed_ids_changed = np.setxor1d(prev_members_arr, next_members_arr)
            typed_ids_all = np.union1d(next_members_arr, prev_members_arr)
        elif next_members_arr is not None:
            typed_ids_changed = np.unique(next_members_arr)
            typed_ids_all = typed_ids_changed
        else:
            assert prev_members_arr is not None
            typed_ids_changed = np.unique(prev_members_arr)
            typed_ids_all = typed_ids_changed

        # Perform full diff if tags changed or contains nested relations
        full_diff: cython.bint = (
            prev is None
            or prev['tags'] != element['tags']
            or np.any(
                (typed_ids_changed >= TYPED_ELEMENT_ID_RELATION_MIN)
                & (typed_ids_changed <= TYPED_ELEMENT_ID_RELATION_MAX)
            ).tolist()
        )

        typed_ids_diff: list[TypedElementId] = (
            typed_ids_all if full_diff else typed_ids_changed
        ).tolist()

        element_state: dict[TypedElementId, ElementStateEntry] = self.element_state
        bbox_points: list[Point] = self._bbox_points
        bbox_refs: set[TypedElementId] = self._bbox_refs

        for typed_id in typed_ids_diff:
            type = element_type(typed_id)

            if type == 'node':
                entry = element_state.get(typed_id)
                if entry is None:
                    bbox_refs.add(typed_id)
                    continue

                point = entry.current.get('point')
                assert point is not None, f'Node {typed_id} point must be set'
                bbox_points.append(point)

            elif type == 'way':
                entry = element_state.get(typed_id)
                if entry is None:
                    bbox_refs.add(typed_id)
                    continue

                members = entry.current['members']
                assert members is not None, f'Way {typed_id} members must be set'

                for node_typed_id in members:
                    entry = element_state.get(node_typed_id)
                    if entry is None:
                        bbox_refs.add(node_typed_id)
                        continue

                    point = entry.current.get('point')
                    assert point is not None, f'Node {node_typed_id} point must be set'
                    bbox_points.append(point)

    async def _preload_changeset(self) -> None:
        """Lock and load changeset state from the database."""
        # Enforce single changeset updates
        changeset_ids = {element['changeset_id'] for element in self._elements}
        if len(changeset_ids) > 1:
            raise_for.diff_multiple_changesets()
        changeset_id = next(iter(changeset_ids))

        # Lock and get changeset
        changeset = await ChangesetQuery.find_by_id(changeset_id, conn=self.conn)
        if changeset is None:
            raise_for.changeset_not_found(changeset_id)

        # Check permissions
        current_user_id = auth_user(required=True)['id']
        if changeset['user_id'] != current_user_id:
            raise_for.changeset_access_denied()

        # Check if changeset is closed
        if changeset['closed_at'] is not None:
            raise_for.changeset_already_closed(changeset_id, changeset['closed_at'])

        self.changeset = changeset

    def _update_changeset_size(
        self, *, num_create: int, num_modify: int, num_delete: int
    ) -> None:
        """Update and validate the changeset size."""
        logging.debug(
            'Optimistic updating changeset %d size (+%d, ~%d, -%d)',
            self.changeset['id'],
            num_create,
            num_modify,
            num_delete,
        )
        if not changeset_increase_size(
            self.changeset,
            num_create=num_create,
            num_modify=num_modify,
            num_delete=num_delete,
        ):
            raise_for.changeset_too_big(
                self.changeset['size'] + num_create + num_modify + num_delete
            )

    async def _update_changeset_bounds(
        self,
        *,
        TYPED_ELEMENT_ID_NODE_MIN: cython.size_t = TYPED_ELEMENT_ID_NODE_MIN,
        TYPED_ELEMENT_ID_NODE_MAX: cython.size_t = TYPED_ELEMENT_ID_NODE_MAX,
    ) -> None:
        """Update changeset bounds using the collected bbox info."""
        bbox_points = self._bbox_points
        bbox_refs = list(self._bbox_refs)

        if bbox_refs:
            logging.debug('Optimistic loading %d bbox elements', len(bbox_refs))
            elements = await ElementQuery.find_by_refs(
                bbox_refs,
                at_sequence_id=self.at_sequence_id,
                recurse_ways=True,
                limit=None,
            )

            for element in elements:
                point = element['point']
                if point is not None:
                    bbox_points.append(point)
                    continue

                typed_id: cython.size_t = element['typed_id']
                if TYPED_ELEMENT_ID_NODE_MIN <= typed_id <= TYPED_ELEMENT_ID_NODE_MAX:
                    logging.warning(
                        'Node %d version %d is missing coordinates',
                        element_id(element['typed_id']),
                        element['version'],
                    )

        if not bbox_points:
            return

        # Update changeset bounds
        new_bounds = extend_changeset_bounds(self.changeset.get('bounds'), bbox_points)
        self.changeset['bounds'] = new_bounds

        # Update union_bounds
        union_bounds = self.changeset['union_bounds']
        if union_bounds is None:
            self.changeset['union_bounds'] = box(*new_bounds.bounds)
        else:
            bounds_arr = bounds([union_bounds, new_bounds])
            self.changeset['union_bounds'] = box(
                bounds_arr[:, 0].min(),
                bounds_arr[:, 1].min(),
                bounds_arr[:, 2].max(),
                bounds_arr[:, 3].max(),
            )

    async def _check_members_remote(self) -> None:
        """Check if the members exist and are visible using the database."""
        elements_check_members_remote = self._elements_check_members_remote
        if not elements_check_members_remote:
            return

        hidden_refs = await ElementQuery.filter_hidden_refs(
            list(elements_check_members_remote),
            at_sequence_id=self.at_sequence_id,
        )
        if not hidden_refs:
            return

        # Find the parent that references this hidden member
        hidden_ref = next(iter(hidden_refs))
        parent_typed_id = elements_check_members_remote[hidden_ref]
        raise_for.element_member_not_found(parent_typed_id, hidden_ref)
