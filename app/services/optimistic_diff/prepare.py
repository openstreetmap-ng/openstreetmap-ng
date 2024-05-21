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
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
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

    apply_elements: list[tuple[Element, ElementRef]]
    """
    Processed elements to be applied into the database.
    """

    _elements: tuple[tuple[Element, ElementRef], ...]
    """
    Input elements processed during the preparation step.
    """

    element_state: defaultdict[ElementRef, list[Element]]
    """
    Local element state, mapping from element ref to that elements history (from oldest to newest).
    """

    _elements_parents_refs: dict[ElementRef, frozenset[ElementRef]]
    """
    Local element parents cache, mapping from element ref to the set of parent element refs.
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

    changeset: Changeset | None
    """
    Local changeset state.
    """

    _bbox_info: set[Point | ElementRef]
    """
    Changeset bounding box info, set of points and element refs.
    """

    def __init__(self, elements: Sequence[Element]) -> None:
        self.at_sequence_id = None
        self.apply_elements = []
        self._elements = tuple((element, ElementRef(element.type, element.id)) for element in elements)
        self.element_state = defaultdict(list)
        self._elements_parents_refs = {}
        self.reference_check_element_refs = set()
        self._reference_override = defaultdict(set)
        self.changeset = None
        self._bbox_info = set()

    async def prepare(self) -> None:
        await self._set_sequence_id()
        async with create_task_group() as tg:
            tg.start_soon(self._preload_elements_state)
            tg.start_soon(self._preload_elements_parents)
            tg.start_soon(self._preload_changeset)

        for element_t in self._elements:
            element, element_ref = element_t
            element_type = element.type
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
                    if not self._check_element_can_delete(element, element_ref):
                        logging.debug('Optimistic skipping delete for %s (is used)', element_ref)
                        continue

            if element_type != 'node':
                # update reference overrides before performing checks
                # then check if all newly referenced members are visible
                # note that elements can self-reference themselves
                # TODO: test this^
                added_members_refs = self._update_reference_override(prev, element, element_ref)
                if added_members_refs is not None:
                    await self._check_members_visible(element, added_members_refs)

            # push bbox info
            self._push_bbox_info(prev, element, element_type)
            # push to the local state
            self.element_state[element_ref].append(element)
            # push to the apply list
            self.apply_elements.append(element_t)

        self._update_changeset_size()
        await self._update_changeset_bounds()

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
        refs: set[ElementRef] = {ref for _, ref in self._elements if ref.id > 0}
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
            for element, element_ref in self._elements  #
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

    def _check_element_can_delete(self, element: Element, element_ref: ElementRef) -> bool:
        """
        Check if the element can be deleted.
        """
        # check if not referenced by local state
        positive_refs = self._reference_override[(element_ref, True)]
        if positive_refs:
            if element.delete_if_unused is True:
                return False
            raise_for().element_in_use(element, positive_refs)

        # check if not referenced by database elements
        # logical optimization, only pre-existing elements
        if element.id < 0:
            return True

        parent_refs = self._elements_parents_refs[element_ref]
        if parent_refs:
            negative_refs = self._reference_override[(element_ref, False)]
            used_by = parent_refs - negative_refs
            if used_by:
                if element.delete_if_unused is True:
                    return False
                raise_for().element_in_use(element, used_by)

        # mark for reference check during apply
        self.reference_check_element_refs.add(element_ref)
        return True

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

    def _push_bbox_info(self, prev: Element | None, element: Element, element_type: ElementType) -> None:
        """
        Push bbox info for later processing.
        """
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
        bbox_info = self._bbox_info
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
        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        union_members = (*next_members, *prev_members)
        node_refs: set[ElementRef] = {ElementRef('node', member.id) for member in union_members}

        bbox_info = self._bbox_info
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

        bbox_info = self._bbox_info
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

    async def _preload_changeset(self) -> None:
        """
        Preload changeset state from the database.
        """
        # currently, enforce single changeset updates
        changeset_ids: set[int] = {element.changeset_id for element, _ in self._elements}
        if len(changeset_ids) > 1:
            raise_for().diff_multiple_changesets()
        changeset_id = next(iter(changeset_ids))

        with options_context(joinedload(Changeset.user)):
            changesets = await ChangesetQuery.find_many_by_query(changeset_ids=(changeset_id,), limit=1)
            changeset = changesets[0] if changesets else None

        if changeset is None:
            raise_for().changeset_not_found(changeset_id)
        if changeset.user_id != auth_user().id:
            raise_for().changeset_access_denied()
        if changeset.closed_at is not None:
            raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

        self.changeset = changeset

    def _update_changeset_size(self) -> None:
        """
        Update and validate changeset size.
        """
        add_size = len(self.apply_elements)
        logging.debug('Optimistic increasing changeset %d size by %d', self.changeset.id, add_size)
        if not self.changeset.increase_size(add_size):
            raise_for().changeset_too_big(self.changeset.size + add_size)

    async def _update_changeset_bounds(self) -> None:
        """
        Update changeset bounds using the collected bbox info.
        """
        # unpack bbox info
        points: list[Point] = []
        elements_refs: set[ElementRef] = set()
        for point_or_ref in self._bbox_info:
            if isinstance(point_or_ref, Point):
                points.append(point_or_ref)
            else:
                elements_refs.add(point_or_ref)

        if elements_refs:
            logging.debug('Optimistic loading %d bbox elements', len(elements_refs))
            elements = await ElementQuery.get_many_by_refs(
                elements_refs,
                at_sequence_id=self.at_sequence_id,
                recurse_ways=True,
                limit=None,
            )

            for element in elements:
                point = element.point
                if point is not None:
                    points.append(point)
                elif element.type == 'node':
                    versioned_ref = VersionedElementRef('node', element.id, element.version)
                    logging.warning('Node %s is missing coordinates', versioned_ref)

        if points:
            self.changeset.union_bounds(unary_union(points))
