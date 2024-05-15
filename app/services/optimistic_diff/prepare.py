import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import cython
from anyio import create_task_group
from shapely import Point
from shapely.ops import unary_union
from sqlalchemy.orm import joinedload

from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.repositories.changeset_repository import ChangesetRepository
from app.repositories.element_repository import ElementRepository


@dataclass(init=False, repr=False, eq=False, match_args=False, slots=True)
class OptimisticDiffPrepare:
    applied: bool
    """
    Indicates if the optimistic diff was applied.
    """

    elements: Sequence[Element]
    """
    Elements the optimistic diff is performed on.
    """

    changeset_state: dict[int, Changeset]
    """
    Local changeset state, mapping from id to the changeset.
    """

    _changeset_bbox_info: dict[int, set[Point | ElementRef]]
    """
    Changeset bbox info, mapping from changeset id to the list of points and element refs.
    """

    element_state: defaultdict[ElementRef, list[Element]]
    """
    Local element state, mapping from element ref to that elements history (from oldest to newest).
    """

    reference_check_element_refs: set[ElementRef]
    """
    Local reference check state, set of element refs that need to be checked for references after last_sequence_id.
    """

    _reference_override: dict[tuple[ElementRef, bool], set[ElementRef]]
    """
    Local reference override, mapping from (element ref, override) tuple to the set of referenced element refs.

    For example, `(way/1, False)` = `{node/1, node/2}` means that way/1 no longer references node/1 and node/2 locally.
    """

    _element_parent_refs_cache: dict[ElementRef, frozenset[ElementRef]]
    """
    Local element parents cache, mapping from element ref to the set of parent element refs.
    """

    last_sequence_id: int

    def __init__(self, elements: Sequence[Element]) -> None:
        self.applied = False
        self.elements = elements
        self.changeset_state = {}
        self._changeset_bbox_info = defaultdict(set)
        self.element_state = defaultdict(list)
        self.reference_check_element_refs = set()
        self._reference_override = defaultdict(set)
        self._element_parent_refs_cache = {}
        self.last_sequence_id = None

    async def prepare(self) -> None:
        """
        Prepare the optimistic update.
        """
        async with create_task_group() as tg:
            # update and validate changesets
            tg.start_soon(self._update_changesets)

            # preload element state
            tg.start_soon(self._preload_elements)

            # assign last element id
            tg.start_soon(self._assign_last_sequence_id_and_check_time_integrity)

        # read property once for performance
        get_latest_elements = self._get_latest_elements
        update_reference_override = self._update_reference_override
        check_element_not_referenced = self._check_element_not_referenced
        check_members_visible = self._check_members_visible
        push_bbox_info = self._push_bbox_info
        push_element_state = self._push_element_state

        for element in self.elements:
            if element.version == 1:
                # action: create
                prev = None

                if element.id >= 0:
                    raise_for().diff_create_bad_id(element.versioned_ref)
            else:
                # action: modify | delete
                prev = (await get_latest_elements((element.element_ref,)))[0]

                if prev.version + 1 != element.version:
                    raise_for().element_version_conflict(element.versioned_ref, prev.version)
                if not prev.visible and not element.visible:
                    raise_for().element_already_deleted(element.versioned_ref)

                now = utcnow()

                if prev.created_at > now:
                    logging.error(
                        'Element %r/%r was created in the future: %r > %r',
                        prev.type,
                        prev.id,
                        prev.created_at,
                        now,
                    )
                    raise_for().time_integrity()

            # update reference overrides before performing checks
            # note that elements can self-reference themselves
            added_members_refs = update_reference_override(prev, element)[1]

            async with create_task_group() as tg:
                # if action==deleted, check if not referenced by other elements
                if (prev is not None) and not element.visible and prev.visible:
                    tg.start_soon(check_element_not_referenced, element)

                # check if all newly referenced members are visible
                if added_members_refs:
                    tg.start_soon(check_members_visible, element, added_members_refs)

            # push the element bbox info
            push_bbox_info(prev, element)

            # push the element to the local state
            push_element_state(element)

        # update changeset boundaries
        await self._update_changeset_boundaries()

    async def _get_changeset(self, changeset_id: int) -> Changeset:
        """
        Get the changeset from the local state or the database if not found.
        """
        if (changeset := self.changeset_state.get(changeset_id)) is not None:
            return changeset

        with options_context(joinedload(Changeset.user)):
            changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)

        if not changesets:
            raise_for().changeset_not_found(changeset_id)

        changeset = changesets[0]

        if changeset.user_id != auth_user().id:
            raise_for().changeset_access_denied()
        if changeset.closed_at is not None:
            raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

        self.changeset_state[changeset_id] = changeset
        return changeset

    async def _update_changesets(self) -> None:
        """
        Update and validate elements changesets.

        Boundaries are not updated as a part of this method.
        """
        if self.changeset_state:
            raise RuntimeError('Cannot update changesets with non-empty local state')

        changeset_id_element_map = defaultdict(list)

        # map changeset id to elements
        for element in self.elements:
            changeset_id_element_map[element.changeset_id].append(element)

        # currently, enforce single changeset updates
        if len(changeset_id_element_map) > 1:
            raise_for().diff_multiple_changesets()

        async def update_changeset_task(changeset_id: int, elements: Sequence[Element]) -> None:
            changeset = await self._get_changeset(changeset_id)
            increase_size = len(elements)

            if not changeset.increase_size(increase_size):
                raise_for().changeset_too_big(changeset.size + increase_size)

        # update and validate changesets (exist, belong to the user, not closed, etc.)
        async with create_task_group() as tg:
            for changeset_id, changeset_elements in changeset_id_element_map.items():
                tg.start_soon(update_changeset_task, changeset_id, changeset_elements)

    async def _preload_elements(self) -> None:
        """
        Preload elements from the database.
        """
        # read property once for performance
        element_state = self.element_state

        if element_state:
            raise RuntimeError('Cannot preload elements with non-empty local state')

        # only preload elements that exist in the database (positive id)
        element_refs: set[ElementRef] = {e.element_ref for e in self.elements if e.id > 0}

        # small optimization
        if not element_refs:
            return

        element_refs_len = len(element_refs)
        elements = await ElementRepository.get_many_by_refs(element_refs, limit=element_refs_len)

        # check if all elements exist
        if len(elements) != element_refs_len:
            for element in elements:
                element_refs.remove(element.element_ref)

            raise_for().element_not_found(next(iter(element_refs)))

        # if they do, push them to the local state
        for element in elements:
            element_state[element.element_ref] = [element]

    async def _assign_last_sequence_id_and_check_time_integrity(self) -> None:
        """
        Remember the last sequence id and check the time integrity.
        """
        if self.last_sequence_id is not None:
            raise RuntimeError('Last sequence id already assigned')

        if (element := await ElementRepository.find_one_latest()) is not None:
            if element.created_at > (now := utcnow()):
                logging.error(
                    'Element %r/%r was created in the future: %r > %r',
                    element.type,
                    element.id,
                    element.created_at,
                    now,
                )
                raise_for().time_integrity()

            self.last_sequence_id = element.sequence_id
        else:
            self.last_sequence_id = 0

    async def _get_latest_elements(self, element_refs_unique: Sequence[ElementRef]) -> Sequence[Element]:
        """
        Get the latest elements from the local state or the database if not found.

        The returned elements order *IS NOT* preserved.
        """
        # read property once for performance
        element_state = self.element_state

        local_elements: list[Element] = []
        remote_refs: list[ElementRef] = []

        for element_ref in element_refs_unique:
            if (elements := element_state.get(element_ref)) is not None:
                # load locally
                local_elements.append(elements[-1])
            else:
                # load remotely
                if element_ref.id < 0:
                    raise_for().element_not_found(element_ref)

                remote_refs.append(element_ref)

        # small optimization
        if not remote_refs:
            return local_elements

        remote_refs_len = len(remote_refs)
        remote_elements = await ElementRepository.get_many_by_refs(remote_refs, limit=remote_refs_len)

        # check if all elements exist
        if len(remote_elements) != remote_refs_len:
            remote_refs_set = set(remote_refs)

            for element in remote_elements:
                remote_refs_set.remove(element.element_ref)

            raise_for().element_not_found(next(iter(remote_refs_set)))

        # update local state
        for element in remote_elements:
            element_state[element.element_ref] = [element]

        return local_elements + remote_elements

    def _push_element_state(self, element: Element) -> None:
        """
        Update the local element state with the new element.
        """
        self.element_state[element.element_ref].append(element)

    def _update_reference_override(
        self,
        prev: Element | None,
        element: Element,
    ) -> tuple[frozenset[ElementRef], frozenset[ElementRef]]:
        """
        Update the local reference overrides.

        Returns the removed and added references.
        """
        prev_refs: frozenset[ElementRef] = prev.members_element_refs_set if (prev is not None) else frozenset()
        next_refs: frozenset[ElementRef] = element.members_element_refs_set

        # read property once for performance
        element_ref = element.element_ref
        reference_override = self._reference_override

        # remove old references
        removed_refs = prev_refs - next_refs
        for ref in removed_refs:
            reference_override[(ref, True)].discard(element_ref)
            reference_override[(ref, False)].add(element_ref)

        # add new references
        added_refs = next_refs - prev_refs
        for ref in added_refs:
            reference_override[(ref, True)].add(element_ref)
            reference_override[(ref, False)].discard(element_ref)

        return removed_refs, added_refs

    async def _check_members_visible(self, initiator: Element, element_refs_unique: Sequence[ElementRef]) -> None:
        """
        Check if the members exists and are visible.
        """
        elements = await self._get_latest_elements(element_refs_unique)

        for element in elements:
            if not element.visible:
                raise_for().element_member_not_found(initiator.versioned_ref, element.element_ref)

    async def _check_element_not_referenced(self, element: Element) -> None:
        """
        Check if the element is not referenced by other elements.
        """
        # read property once for performance
        reference_override = self._reference_override
        element_parent_refs_cache = self._element_parent_refs_cache
        element_ref = element.element_ref

        # check if not referenced by local state
        positive_refs = reference_override[(element_ref, True)]
        if positive_refs:
            raise_for().element_in_use(element.versioned_ref, positive_refs)

        # check if not referenced by database elements
        # logical optimization, only pre-existing elements
        if element.id > 0:
            negative_refs = reference_override[(element_ref, False)]
            parent_refs = element_parent_refs_cache.get(element_ref)

            if parent_refs is None:
                # cache miss, fetch from the database
                parents = await ElementRepository.get_many_parents_by_refs(
                    (element_ref,),
                    limit=len(negative_refs) + 1,
                )

                last_sequence_id = self.last_sequence_id
                parent_refs_list: list[ElementRef] = []

                for parent in parents:
                    parent_sequence_id = parent.sequence_id
                    parent_ref = parent.element_ref

                    if parent_sequence_id > last_sequence_id:
                        raise OptimisticDiffError(
                            f'Parent {parent_ref} has future sequence id {parent_sequence_id} > {last_sequence_id}'
                        )

                    parent_refs_list.append(parent_ref)

                parent_refs = frozenset(parent_refs_list)
                element_parent_refs_cache[element_ref] = parent_refs

            for parent_ref in parent_refs - negative_refs:
                raise_for().element_in_use(element.versioned_ref, (parent_ref,))

            self.reference_check_element_refs.add(element_ref)

    def _push_bbox_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for later processing.
        """
        element_type = element.type
        if element_type == 'node':
            self._push_bbox_node_info(prev, element)
        elif element_type == 'way':
            self._push_bbox_way_info(prev, element)
        elif element_type == 'relation':
            self._push_bbox_relation_info(prev, element)
        else:
            raise NotImplementedError(f'Unsupported element type {element_type!r}')

    def _push_bbox_node_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a node.
        """
        bbox_info = self._changeset_bbox_info[element.changeset_id]

        element_point = element.point
        if element_point is not None:
            bbox_info.add(element_point)

        if prev is not None:
            prev_point = prev.point
            if prev_point is not None:
                bbox_info.add(prev_point)

    def _push_bbox_way_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a way.

        Way info contains all nodes.
        """
        # read property once for performance
        element_state = self.element_state

        bbox_info = self._changeset_bbox_info[element.changeset_id]
        prev_refs: frozenset[ElementRef] = prev.members_element_refs_set if (prev is not None) else frozenset()
        next_refs: frozenset[ElementRef] = element.members_element_refs_set

        union_refs = next_refs | prev_refs

        for element_ref in union_refs:
            if (elements := element_state.get(element_ref)) is not None:
                bbox_info.add(elements[-1].point)
            else:
                bbox_info.add(element_ref)

    def _push_bbox_relation_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a relation.

        Relation info contains either all members or only changed members.
        """
        # read property once for performance
        element_state = self.element_state

        bbox_info = self._changeset_bbox_info[element.changeset_id]
        prev_refs: frozenset[ElementRef] = prev.members_element_refs_set if (prev is not None) else frozenset()
        next_refs: frozenset[ElementRef] = element.members_element_refs_set

        changed_refs = prev_refs ^ next_refs

        # check for changed tags
        full_diff: cython.char = (prev is None) or (prev.tags != element.tags)

        # check for any relation members
        if not full_diff:
            for ref in changed_refs:
                if ref.type == 'relation':
                    full_diff = True
                    break

        diff_refs = (prev_refs | next_refs) if full_diff else (changed_refs)

        for element_ref in diff_refs:
            if element_ref.type == 'node':
                if (elements := element_state.get(element_ref)) is None:
                    bbox_info.add(elements[-1].point)
                else:
                    bbox_info.add(element_ref)

            elif element_ref.type == 'way':
                if (elements := element_state.get(element_ref)) is None:
                    bbox_info.add(element_ref)
                    continue

                for member_ref in elements[-1].members:
                    member_element_ref = member_ref.element_ref
                    if (member_elements := element_state.get(member_element_ref)) is not None:
                        bbox_info.add(member_elements[-1].point)
                    else:
                        bbox_info.add(member_element_ref)

    async def _update_changeset_boundaries(self) -> None:
        """
        Update changeset boundaries using the bbox info.
        """

        async def task(changeset_id: int, bbox_info: set[Point | ElementRef]) -> None:
            points: list[Point] = []
            element_refs_map: set[ElementRef] = set()

            # organize bbox info into points and element refs
            for point_or_ref in bbox_info:
                if isinstance(point_or_ref, Point):
                    points.append(point_or_ref)
                else:
                    element_refs_map.add(point_or_ref)

            # get points for element refs
            elements = await ElementRepository.get_many_by_refs(
                element_refs_map,
                recurse_ways=True,
                limit=None,
            )

            for element in elements:
                element_point = element.point

                if element_point is not None:
                    points.append(element_point)
                elif element.type == 'node':
                    raise ValueError(f'Node {element.id} is missing coordinates')

            # update changeset bounds if any points
            if points:
                changeset = await self._get_changeset(changeset_id)
                changeset.union_bounds(unary_union(points))

        # start task for each changeset
        async with create_task_group() as tg:
            for changeset_id, bbox_info in self._changeset_bbox_info.items():
                tg.start_soon(task, changeset_id, bbox_info)
