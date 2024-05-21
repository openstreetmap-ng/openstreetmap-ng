import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import cython
from anyio import create_task_group
from shapely import Point
from shapely.ops import unary_union
from sqlalchemy.orm import joinedload

from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.osmchange_action import OSMChangeAction
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery


@dataclass(init=False, repr=False, eq=False, match_args=False, slots=True)
class OptimisticDiffPrepare:
    at_sequence_id: int | None
    """
    sequence_id at which the optimistic diff is performed.
    """

    elements: Sequence[Element]
    """
    Elements the optimistic diff is performed on.
    """

    _elements_refs: tuple[ElementRef, ...]
    """
    Elements refs the optimistic diff is performed on.
    """

    element_state: defaultdict[ElementRef, list[Element]]
    """
    Local element state, mapping from element ref to that elements history (from oldest to newest).
    """

    _elements_parents_refs: dict[ElementRef, frozenset[ElementRef]]
    """
    Local element parents cache, mapping from element ref to the set of parent element refs.
    """

    changeset_state: dict[int, Changeset]
    """
    Local changeset state, mapping from id to the changeset.
    """

    _changeset_bbox_info: dict[int, set[Point | ElementRef]]
    """
    Changeset bbox info, mapping from changeset id to the list of points and element refs.
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

    def __init__(self, elements: Sequence[Element]) -> None:
        self.at_sequence_id = None
        self.elements = elements
        self._elements_refs = tuple(ElementRef(element.type, element.id) for element in elements)
        self.element_state = defaultdict(list)
        self._elements_parents_refs = {}
        self.changeset_state = {}
        self._changeset_bbox_info = defaultdict(set)
        self.reference_check_element_refs = set()
        self._reference_override = defaultdict(set)

    async def prepare(self) -> None:
        await self._set_sequence_id()
        async with create_task_group() as tg:
            tg.start_soon(self._preload_elements_state)
            tg.start_soon(self._preload_elements_parents)
            tg.start_soon(self._update_changesets_sizes)

        for element, element_ref in zip(self.elements, self._elements_refs, strict=True):
            action: OSMChangeAction

            if element.version == 1:
                action = 'create'
                prev = None

                if element.id >= 0:
                    raise_for().diff_create_bad_id(element)
            else:
                action = 'modify' if element.visible else 'delete'
                prevs = await self._get_elements_by_refs((element_ref,))
                prev = prevs[0]

                if prev.version + 1 != element.version:
                    raise_for().element_version_conflict(element, prev.version)

                if action == 'delete':
                    if not prev.visible:
                        raise_for().element_already_deleted(element)

                    # on delete, check if not referenced by other elements
                    self._check_element_unreferenced(element, element_ref)

            if element.type != 'node':
                # update reference overrides before performing checks
                # the check if all newly referenced members are visible
                # note that elements can self-reference themselves
                # TODO: test this^
                added_members_refs = self._update_reference_override(prev, element, element_ref)
                if added_members_refs is not None:
                    await self._check_members_visible(element, added_members_refs)

            # push the element bbox info
            self._push_bbox_info(prev, element)
            # push the element to the local state
            self.element_state[element_ref].append(element)

        await self._update_changeset_boundaries()

    async def _set_sequence_id(self) -> None:
        """
        Set the current sequence_id.
        """
        if self.at_sequence_id is not None:
            raise AssertionError('at_sequence_id is already assigned')

        self.at_sequence_id = await ElementQuery.get_current_sequence_id()
        logging.debug('Optimistic preparing at sequence_id %d', self.at_sequence_id)

    async def _preload_elements_state(self) -> None:
        """
        Preload elements state from the database.
        """
        # only preload elements that exist in the database (positive id)
        refs: set[ElementRef] = {ref for ref in self._elements_refs if ref.id > 0}
        if not refs:
            return

        refs_len = len(refs)
        logging.debug('Optimistic preloading %d elements', refs_len)
        elements = await ElementQuery.get_many_by_refs(
            refs,
            at_sequence_id=self.at_sequence_id,
            limit=refs_len,
        )

        # check if all elements exist
        if len(elements) != refs_len:
            for element in elements:
                refs.remove(ElementRef(element.type, element.id))
            raise_for().element_not_found(next(iter(refs)))

        # if they do, push them to the local state
        element_state = self.element_state
        for element in elements:
            element_state[ElementRef(element.type, element.id)] = [element]

        logging.debug('Optimistic preloading members for %d elements', refs_len)
        await ElementMemberQuery.resolve_members(elements)

    async def _preload_elements_parents(self) -> None:
        """
        Preload elements parents from the database.
        """
        # only preload elements that exist in the database (positive id) and will be deleted
        refs: set[ElementRef] = {
            element_ref
            for element, element_ref in zip(self.elements, self._elements_refs, strict=True)
            if element.id > 0 and not element.visible
        }
        if not refs:
            return

        refs_len = len(refs)
        logging.debug('Optimistic preloading parents for %d elements', refs_len)
        member_parents_map = await ElementQuery.get_many_parents_refs_by_refs(
            refs,
            at_sequence_id=self.at_sequence_id,
            limit=None,
        )
        self._elements_parents_refs = {
            member_ref: frozenset(parents_refs)  #
            for member_ref, parents_refs in member_parents_map.items()
        }

    async def _get_elements_by_refs(self, element_refs_unique: Iterable[ElementRef]) -> Sequence[Element]:
        """
        Get the latest elements from the local state or the database.
        """
        local_elements: list[Element] = []
        remote_refs: list[ElementRef] = []

        element_state = self.element_state
        for element_ref in element_refs_unique:
            elements = element_state.get(element_ref)
            if elements is not None:
                # load locally
                local_elements.append(elements[-1])
            else:
                # load remotely
                if element_ref.id < 0:
                    raise_for().element_not_found(element_ref)
                remote_refs.append(element_ref)

        if not remote_refs:
            return local_elements

        remote_refs_len = len(remote_refs)
        logging.debug('Optimistic loading %d elements', remote_refs_len)
        remote_elements = await ElementQuery.get_many_by_refs(
            remote_refs,
            at_sequence_id=self.at_sequence_id,
            limit=remote_refs_len,
        )

        # check if all elements exist
        if len(remote_elements) != remote_refs_len:
            remote_refs_set = set(remote_refs)
            for element in remote_elements:
                remote_refs_set.remove(ElementRef(element.type, element.id))
            raise_for().element_not_found(next(iter(remote_refs_set)))

        # update local state
        for element in remote_elements:
            element_state[ElementRef(element.type, element.id)] = [element]

        logging.debug('Optimistic loading members for %d elements', remote_refs_len)
        await ElementMemberQuery.resolve_members(remote_elements)
        return local_elements + remote_elements

    async def _update_changesets_sizes(self) -> None:
        """
        Update and validate changesets sizes.
        """
        # map changeset id to elements
        changeset_id_elements_map = defaultdict(list)
        for element in self.elements:
            changeset_id_elements_map[element.changeset_id].append(element)

        # currently, enforce single changeset updates
        if len(changeset_id_elements_map) > 1:
            raise_for().diff_multiple_changesets()

        async def task(changeset_id: int, elements: Sequence[Element]) -> None:
            logging.debug('Optimistic updating changeset %d', changeset_id)

            with options_context(joinedload(Changeset.user)):
                changeset = await self._get_open_changeset(changeset_id)

            add_size = len(elements)
            if not changeset.increase_size(add_size):
                raise_for().changeset_too_big(changeset.size + add_size)

        # update and validate changesets (exist, belong to the user, not closed, etc.)
        async with create_task_group() as tg:
            for changeset_id, changeset_elements in changeset_id_elements_map.items():
                tg.start_soon(task, changeset_id, changeset_elements)

    async def _get_open_changeset(self, changeset_id: int) -> Changeset:
        """
        Get the changeset from the local state or the database.
        """
        # check local state first
        changeset = self.changeset_state.get(changeset_id)
        if changeset is not None:
            return changeset

        # fallback to database query
        changesets = await ChangesetQuery.find_many_by_query(changeset_ids=(changeset_id,), limit=1)
        changeset = changesets[0] if changesets else None
        if changeset is None:
            raise_for().changeset_not_found(changeset_id)
        if changeset.user_id != auth_user().id:
            raise_for().changeset_access_denied()
        if changeset.closed_at is not None:
            raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

        self.changeset_state[changeset_id] = changeset
        return changeset

    def _update_reference_override(
        self,
        prev: Element | None,
        element: Element,
        element_ref: ElementRef,
    ) -> frozenset[ElementRef] | None:
        """
        Update the local reference overrides.

        Returns the newly added references if any.
        """
        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        if not next_members and not prev_members:
            return None

        next_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in next_members}
        prev_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in prev_members}
        reference_override = self._reference_override

        # remove old references
        if prev_members:
            removed_refs = prev_refs - next_refs
            for ref in removed_refs:
                reference_override[(ref, True)].discard(element_ref)
                reference_override[(ref, False)].add(element_ref)

        # add new references
        if next_members:
            added_refs = next_refs - prev_refs
            for ref in added_refs:
                reference_override[(ref, True)].add(element_ref)
                reference_override[(ref, False)].discard(element_ref)
            return frozenset(added_refs)

        return None

    async def _check_members_visible(self, parent: Element, member_refs: frozenset[ElementRef]) -> None:
        """
        Check if the members exist and are visible.
        """
        elements = await self._get_elements_by_refs(member_refs)
        for element in elements:
            if not element.visible:
                raise_for().element_member_not_found(parent, ElementRef(element.type, element.id))

    def _check_element_unreferenced(self, element: Element, element_ref: ElementRef) -> None:
        """
        Check if the element is unreferenced.
        """
        # check if not referenced by local state
        positive_refs = self._reference_override[(element_ref, True)]
        if positive_refs:
            raise_for().element_in_use(element, positive_refs)

        # check if not referenced by database elements
        # logical optimization, only pre-existing elements
        if element.id < 0:
            return

        # mark for reference check during apply
        # TODO: only when actually deleting the element
        self.reference_check_element_refs.add(element_ref)

        parent_refs = self._elements_parents_refs[element_ref]
        if not parent_refs:
            return

        negative_refs = self._reference_override[(element_ref, False)]
        used_by = parent_refs - negative_refs
        if used_by:
            raise_for().element_in_use(element, used_by)

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
        bbox_info = self._changeset_bbox_info[element.changeset_id]

        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        union_members = (*next_members, *prev_members)
        node_refs: set[ElementRef] = {ElementRef('node', member.id) for member in union_members}

        element_state = self.element_state
        for node_ref in node_refs:
            nodes = element_state.get(node_ref)
            if nodes is not None:
                bbox_info.add(nodes[-1].point)
            else:
                bbox_info.add(node_ref)

    def _push_bbox_relation_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a relation.

        Relation info contains either all members or only changed members.
        """
        bbox_info = self._changeset_bbox_info[element.changeset_id]

        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        next_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in next_members}
        prev_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in prev_members}
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

        element_state = self.element_state
        for member_ref in diff_refs:
            member_type = member_ref.type

            if member_type == 'node':
                nodes = element_state.get(member_ref)
                if nodes is not None:
                    bbox_info.add(nodes[-1].point)
                else:
                    bbox_info.add(member_ref)

            elif member_type == 'way':
                ways = element_state.get(member_ref)
                if ways is None:
                    bbox_info.add(member_ref)
                    continue

                for node_member in ways[-1].members:
                    node_ref = ElementRef('node', node_member.id)
                    nodes = element_state.get(node_ref)
                    if nodes is not None:
                        bbox_info.add(nodes[-1].point)
                    else:
                        bbox_info.add(node_ref)

    async def _update_changeset_boundaries(self) -> None:
        """
        Update changeset boundaries using the collected bbox info.
        """

        async def task(changeset_id: int, bbox_info: set[Point | ElementRef]) -> None:
            # unpack bbox info
            points: list[Point] = []
            refs_set: set[ElementRef] = set()
            for point_or_ref in bbox_info:
                if isinstance(point_or_ref, Point):
                    points.append(point_or_ref)
                else:
                    refs_set.add(point_or_ref)

            if refs_set:
                logging.debug('Optimistic loading %d bbox elements', len(refs_set))
                elements = await ElementQuery.get_many_by_refs(
                    refs_set,
                    at_sequence_id=self.at_sequence_id,
                    recurse_ways=True,
                    limit=None,
                )

                for element in elements:
                    point = element.point
                    if point is not None:
                        points.append(point)
                    elif element.type == 'node':
                        logging.warning('Node %dv%d is missing coordinates', element.id, element.version)

            if points:
                changeset = self.changeset_state[changeset_id]
                changeset.union_bounds(unary_union(points))

        async with create_task_group() as tg:
            for changeset_id, bbox_info in self._changeset_bbox_info.items():
                tg.start_soon(task, changeset_id, bbox_info)
