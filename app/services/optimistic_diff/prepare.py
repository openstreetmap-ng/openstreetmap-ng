import logging
from collections import defaultdict
from collections.abc import Sequence
from itertools import chain

import anyio
from shapely import Point
from shapely.ops import unary_union

from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.repositories.element_repository import ElementRepository

# read property once for performance
_type_node = ElementType.node
_type_way = ElementType.way
_type_relation = ElementType.relation


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

    element_state: dict[ElementRef, list[Element]]
    """
    Local element state, mapping from element ref to that elements history (from oldest to newest).
    """

    reference_check_state: dict[ElementRef, tuple[Element, int]]
    """
    Local reference check state, mapping from element ref to that element and the last referencing element id.
    """

    _reference_override: dict[tuple[ElementRef, bool], set[ElementRef]]
    """
    Local reference override, mapping from (element ref, override) tuple to the set of referenced element refs.

    For example, `(way/1, False)` = `{node/1, node/2}` means that way/1 no longer references node/1 and node/2 locally.
    """

    _last_sequence_id: int

    def __init__(self, elements: Sequence[Element]) -> None:
        self.applied = False
        self.elements = elements
        self.changeset_state = {}
        self._changeset_bbox_info = defaultdict(set)
        self.element_state = {}
        self.reference_check_state = {}
        self._reference_override = defaultdict(set)
        self._last_sequence_id = None

    async def prepare(self) -> None:
        """
        Prepare the optimistic update.
        """

        async with anyio.create_task_group() as tg:
            # update and validate changesets
            tg.start_soon(self._update_changesets)

            # preload element state
            tg.start_soon(self._preload_elements)

            # assign last element id
            tg.start_soon(self._assign_last_sequence_id_and_check_time_integrity)

        for element in self.elements:
            if element.version == 1:
                # action: create
                prev = None

                if element.id >= 0:
                    raise_for().diff_create_bad_id(element.versioned_ref)
            else:
                # action: modify | delete
                prev = await self._get_latest_element(element.element_ref)

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
            self._update_reference_override(prev, element)

            async with anyio.create_task_group() as tg:
                # check if all referenced elements are visible
                # TODO: check only added members?
                for element_ref in (e.element_ref for e in element.members):
                    tg.start_soon(self._check_member_visible, element, element_ref)

                # if deleted, check if not referenced by other elements
                if not element.visible and prev and prev.visible:
                    tg.start_soon(self._check_element_not_referenced, element)

            # push the element bbox info
            self._push_bbox_info(prev, element)

            # push the element to the local state
            self._push_element_state(element)

        # update changeset boundaries
        await self._update_changeset_boundaries()

    async def _get_changeset(self, changeset_id: int) -> Changeset:
        """
        Get the changeset from the local state or the database if not found.
        """

        if (changeset := self.changeset_state.get(changeset_id)) is not None:
            return changeset

        changeset = await Changeset.find_one_by_id(changeset_id)

        if changeset is None:
            raise_for().changeset_not_found(changeset_id)
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
            raise RuntimeError('Cannot update changesets when local state is not empty')

        async def update_changeset(changeset_id: int, elements: Sequence[Element]) -> None:
            changeset = await self._get_changeset(changeset_id)
            increase_size = len(elements)

            if not changeset.increase_size(increase_size):
                raise_for().changeset_too_big(changeset.size + increase_size)

        changeset_id_element_map = defaultdict(list)

        # map changeset id to elements
        for element in self.elements:
            changeset_id_element_map[element.changeset_id].append(element)

        # currently, enforce single changeset updates
        if len(changeset_id_element_map) > 1:
            raise_for().diff_multiple_changesets()

        # update and validate changesets (exist, belong to the user, not closed, etc.)
        async with anyio.create_task_group() as tg:
            for changeset_id, changeset_elements in changeset_id_element_map.items():
                tg.start_soon(update_changeset, changeset_id, changeset_elements)

    async def _preload_elements(self) -> None:
        """
        Preload elements from the database.
        """

        if self.element_state:
            raise RuntimeError('Cannot preload elements when local state is not empty')

        # only preload elements that exist in the database (positive id)
        element_refs = {e.element_ref for e in self.elements if e.id > 0}

        # small optimization
        if not element_refs:
            return

        elements = await ElementRepository.get_many_latest_by_element_refs(element_refs, limit=len(element_refs))

        # check if all elements exist
        if len(elements) != len(element_refs):
            for element in elements:
                element_refs.remove(element.element_ref)

            raise_for().element_not_found(next(iter(element_refs)))

        # if they do, push them to the local state
        for element_ref, element in zip(element_refs, elements, strict=True):
            self.element_state[element_ref] = [element]

    async def _assign_last_sequence_id_and_check_time_integrity(self) -> None:
        """
        Remember the last sequence id and check the time integrity.
        """

        if self._last_sequence_id is not None:
            raise RuntimeError('Cannot fetch last id when already fetched')

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

            self._last_sequence_id = element.sequence_id
        else:
            self._last_sequence_id = 0

    async def _get_latest_element(self, element_ref: ElementRef) -> Element:
        """
        Get the latest element from the local state or the database if not found.
        """

        # check if exists in local state
        if (elements := self.element_state.get(element_ref)) is not None:
            return elements[-1]

        # fetch from database if id is valid
        if element_ref.id < 0:
            raise_for().element_not_found(element_ref)
        if not (elements := await ElementRepository.get_many_latest_by_element_refs((element_ref,), limit=1)):
            raise_for().element_not_found(element_ref)

        # update local state
        element = elements[0]
        self.element_state[element_ref] = [element]
        return element

    def _push_element_state(self, element: Element) -> None:
        """
        Update the local element state with the new element.
        """

        if (elements := self.element_state.get(element.element_ref)) is not None:
            # if history exists, append to it
            elements.append(element)
        else:
            # otherwise, create a new history
            self.element_state[element.element_ref] = [element]

    def _update_reference_override(self, prev: Element | None, element: Element) -> None:
        """
        Update the local reference overrides.
        """

        prev_refs = prev.references if prev is not None else frozenset()
        next_refs = element.references

        # read property once for performance
        element_ref = element.element_ref

        # remove old references
        for ref in prev_refs - next_refs:
            self._reference_override[(ref, True)].discard(element_ref)
            self._reference_override[(ref, False)].add(element_ref)

        # add new references
        for ref in next_refs - prev_refs:
            self._reference_override[(ref, True)].add(element_ref)
            self._reference_override[(ref, False)].discard(element_ref)

    async def _check_member_visible(self, initiator: Element, element_ref: ElementRef) -> None:
        """
        Check if the member exists and is visible.
        """

        try:
            if not (await self._get_latest_element(element_ref)).visible:
                raise Exception
        except Exception:
            # convert all exceptions to element member not found
            raise_for().element_member_not_found(initiator.versioned_ref, element_ref)

    async def _check_element_not_referenced(self, element: Element) -> None:
        """
        Check if the element is not referenced by other elements.
        """

        # check if not referenced by local state
        if refs := self._reference_override[(element.element_ref, True)]:
            raise_for().element_in_use(element.versioned_ref, refs)

        # check if not referenced by database elements (only existing elements)
        if element.id > 0:
            negative_refs = self._reference_override[(element.element_ref, False)]
            parents = await ElementRepository.get_many_parents_by_element_refs(
                (element.element_ref,),
                limit=len(negative_refs) + 1,
            )
            parent_refs = {e.element_ref for e in parents}
            if refs := (parent_refs - negative_refs):
                raise_for().element_in_use(element.versioned_ref, refs)

            # remember the last referencing element id for the future reference check
            referenced_by_last_sequence_id = self.reference_check_state.get(element.element_ref, self._last_sequence_id)

            for parent in parents:
                referenced_by_last_sequence_id = max(referenced_by_last_sequence_id, parent.sequence_id)

            self.reference_check_state[element.element_ref] = referenced_by_last_sequence_id

    def _push_bbox_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for later processing.
        """

        if element.type == _type_node:
            self._push_bbox_node_info(prev, element)
        elif element.type == _type_way:
            self._push_bbox_way_info(prev, element)
        elif element.type == _type_relation:
            self._push_bbox_relation_info(prev, element)
        else:
            raise NotImplementedError(f'Unsupported element type {element.type!r}')

    def _push_bbox_node_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a node.
        """

        bbox_info = self._changeset_bbox_info[element.changeset_id]

        if element.point is not None:
            bbox_info.add(element.point)
        if (prev is not None) and (prev.point is not None):
            bbox_info.add(prev.point)

    def _push_bbox_way_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a way.

        Way info contains all nodes.
        """

        bbox_info = self._changeset_bbox_info[element.changeset_id]
        pref_refs = prev.members if prev is not None else ()
        next_refs = element.members

        for element_ref in {e.element_ref for e in chain(pref_refs, next_refs)}:
            if (elements := self.element_state.get(element_ref)) is not None:
                bbox_info.add(elements[-1].point)
            else:
                bbox_info.add(element_ref)

    def _push_bbox_relation_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a relation.

        Relation info contains either all members or only changed members.
        """

        bbox_info = self._changeset_bbox_info[element.changeset_id]
        prev_refs = frozenset(prev.members) if prev is not None else frozenset()
        next_refs = frozenset(element.members)
        changed_refs = prev_refs ^ next_refs
        contains_relation = any(ref.type == _type_relation for ref in changed_refs)
        tags_changed = prev is None or prev.tags != element.tags

        # get full geometry or changed geometry
        diff_refs = (prev_refs | next_refs) if (tags_changed or contains_relation) else (changed_refs)

        for element_ref in (e.element_ref for e in diff_refs):
            if element_ref.type == _type_relation:
                continue
            if (elements := self.element_state.get(element_ref)) is not None:
                bbox_info.add(elements[-1].point)
            else:
                bbox_info.add(element_ref)

    async def _update_changeset_boundaries(self) -> None:
        """
        Update changeset boundaries using the bbox info.
        """

        async def task(changeset_id: int, bbox_info: set[Point | ElementRef]) -> None:
            points = set()
            element_refs = set()

            # organize bbox info into points and element refs
            for point_or_ref in bbox_info:
                if isinstance(point_or_ref, Point):
                    points.add(point_or_ref)
                else:
                    element_refs.add(point_or_ref)

            # get points for element refs
            elements = await ElementRepository.get_many_latest_by_element_refs(
                element_refs,
                recurse_ways=True,
                limit=None,
            )

            for element in elements:
                if element.point is not None:
                    points.add(element.point)
                elif element.type == _type_node:
                    # log warning as this should not happen
                    logging.warning('Node %r has no point', element.id)

            # update changeset bounds if any points
            if points:
                changeset = await self._get_changeset(changeset_id)
                changeset.union_bounds(unary_union(points))

        # start task for each changeset
        async with anyio.create_task_group() as tg:
            for changeset_id, bbox_info in self._changeset_bbox_info.items():
                tg.start_soon(task, changeset_id, bbox_info)
