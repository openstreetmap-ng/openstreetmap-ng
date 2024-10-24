import logging
from asyncio import TaskGroup
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from itertools import chain
from typing import Final, Literal

import cython
from shapely import Point, box, multipolygons
from sqlalchemy.orm import joinedload

from app.lib.auth_context import auth_user
from app.lib.change_bounds import change_bounds
from app.lib.exceptions_context import raise_for
from app.lib.options_context import options_context
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.models.element import ElementRef, ElementType, VersionedElementRef
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery

OSMChangeAction = Literal['create', 'modify', 'delete']


class ElementStateEntry:
    __slots__ = ('remote', 'current')

    remote: Final[Element | None]
    current: Element

    def __init__(self, *, remote: Element | None, current: Element):
        self.remote = remote
        self.current = current


@dataclass(slots=True)
class OptimisticDiffPrepare:
    at_sequence_id: int
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

    element_state: dict[ElementRef, ElementStateEntry]
    """
    Local element state, mapping from element ref to remote and local elements.
    """

    _elements_parents_refs: dict[ElementRef, frozenset[ElementRef]]
    """
    Local element parents cache, mapping from element ref to the set of parent element refs.
    """

    _elements_check_members_remote: list[tuple[ElementRef, set[ElementRef]]]
    """
    List of element refs and their member refs to be checked remotely.
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

    _bbox_points: list[Point]
    """
    Changeset bounding box collection of points.
    """

    _bbox_refs: set[ElementRef]
    """
    Changeset bounding box set of element refs.
    """

    def __init__(self, elements: Collection[Element]) -> None:
        self.at_sequence_id = 0
        self.apply_elements = []
        self._elements = tuple((element, ElementRef(element.type, element.id)) for element in elements)
        self.element_state = {}
        self._elements_parents_refs = {}
        self._elements_check_members_remote = []
        self.reference_check_element_refs = set()
        self._reference_override = defaultdict(set)
        self.changeset = None
        self._bbox_points = []
        self._bbox_refs = set()

    async def prepare(self) -> None:
        await self._set_sequence_id()
        async with TaskGroup() as tg:
            tg.create_task(self._preload_elements_state())
            tg.create_task(self._preload_elements_parents())
            tg.create_task(self._preload_changeset())

        for element_t in self._elements:
            element, element_ref = element_t
            element_type = element.type

            action: OSMChangeAction
            entry: ElementStateEntry | None
            prev: Element | None
            if element.version == 1:
                action = 'create'

                if element.id >= 0:
                    raise_for().diff_create_bad_id(element)
                if element_ref in self.element_state:
                    raise AssertionError(f'Element {element_ref!r} must not exist in the element state')

                entry = None
                prev = None
            else:
                action = 'modify' if element.visible else 'delete'
                entry = self.element_state.get(element_ref)
                if entry is None:
                    raise_for().element_not_found(element_ref)

                prev = entry.current
                if prev.version + 1 != element.version:
                    raise_for().element_version_conflict(element, prev.version)
                if action == 'delete' and not prev.visible:
                    raise_for().element_already_deleted(element)

            # update references and check if all newly added members are valid
            if element_type != 'node':
                added_members_refs = self._update_reference_override(prev, element, element_ref)
                if added_members_refs:
                    self._check_members_local(element, element_ref, added_members_refs)

            # on delete, check if not referenced by other elements
            if action == 'delete' and not self._check_element_can_delete(element, element_ref):
                logging.debug('Optimistic skipping delete for %s (is used)', element_ref)
                continue

            self._push_bbox_info(prev, element, element_type)
            self.apply_elements.append(element_t)

            if entry is None:
                self.element_state[element_ref] = ElementStateEntry(remote=None, current=element)
            else:
                entry.current = element

        self._update_changeset_size()
        async with TaskGroup() as tg:
            tg.create_task(self._update_changeset_bounds())
            tg.create_task(self._check_members_remote())

    async def _set_sequence_id(self) -> None:
        """
        Set the current sequence_id.
        """
        if self.at_sequence_id > 0:
            raise AssertionError('Sequence id must not be set')
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
        elements = await ElementQuery.get_by_refs(
            refs,
            at_sequence_id=self.at_sequence_id,
            limit=refs_len,
        )

        # check if all elements exist
        if len(elements) != refs_len:
            refs.difference_update(ElementRef(element.type, element.id) for element in elements)
            element_ref = next(iter(refs))
            raise_for().element_not_found(element_ref)

        # if they do, push them to the element state
        self.element_state = {
            ElementRef(element.type, element.id): ElementStateEntry(remote=element, current=element)
            for element in elements
        }

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
        member_parents_map = await ElementQuery.get_parents_refs_by_refs(
            refs,
            at_sequence_id=self.at_sequence_id,
            limit=None,
        )
        self._elements_parents_refs = {
            member_ref: frozenset(parents_refs)  #
            for member_ref, parents_refs in member_parents_map.items()
        }

    def _check_element_can_delete(self, element: Element, element_ref: ElementRef) -> bool:
        """
        Check if the element can be deleted.
        """
        # check if not referenced by element state
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
    ) -> set[ElementRef] | None:
        """
        Update the local reference overrides.

        Returns the newly added references if any.
        """
        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        if next_members is None or prev_members is None:
            raise AssertionError('Element members must be set')
        if not next_members and not prev_members:
            return None

        next_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in next_members}
        prev_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in prev_members}
        reference_override = self._reference_override

        # remove old references
        if prev_members:
            removed_refs = prev_refs.difference(next_refs)
            for ref in removed_refs:
                reference_override[(ref, True)].discard(element_ref)
                reference_override[(ref, False)].add(element_ref)

        # add new references
        if next_members:
            added_refs = next_refs.difference(prev_refs)
            for ref in added_refs:
                reference_override[(ref, True)].add(element_ref)
                reference_override[(ref, False)].discard(element_ref)
            return added_refs

        return None

    def _check_members_local(self, parent: Element, parent_ref: ElementRef, member_refs: set[ElementRef]) -> None:
        """
        Check if the members exist and are visible using element state.

        Store the not found member refs for remote check.
        """
        notfound: set[ElementRef] = set()
        element_state = self.element_state
        for member_ref in member_refs:
            entry = element_state.get(member_ref)
            if entry is None and member_ref == parent_ref:  # self-reference during creation
                if not parent.visible:
                    raise_for().element_member_not_found(parent_ref, member_ref)
                continue
            if entry is None:
                notfound.add(member_ref)
                continue
            if not entry.current.visible:
                raise_for().element_member_not_found(parent_ref, member_ref)

        if notfound:
            self._elements_check_members_remote.append((parent_ref, notfound))

    async def _check_members_remote(self) -> None:
        """
        Check if the members exist and are visible using the database.
        """
        remote_refs: set[ElementRef] = set()
        for _, member_refs in self._elements_check_members_remote:
            remote_refs.update(member_refs)
        if not remote_refs:
            return

        visible_refs = await ElementQuery.filter_visible_refs(remote_refs, at_sequence_id=self.at_sequence_id)
        hidden_refs = remote_refs.difference(visible_refs)
        hidden_ref = next(iter(hidden_refs), None)
        if hidden_ref is None:
            return

        # contains a non-visible member, determine the parent ref for a nicer error message
        for parent_ref, member_refs in self._elements_check_members_remote:
            if hidden_ref in member_refs:
                raise_for().element_member_not_found(parent_ref, hidden_ref)

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
        bbox_points = self._bbox_points
        element_point = element.point
        if element_point is not None:
            bbox_points.append(element_point)

        if prev is not None:
            prev_point = prev.point
            if prev_point is not None:
                bbox_points.append(prev_point)

    def _push_bbox_way_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a way.

        Way info contains all nodes.
        """
        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        if next_members is None or prev_members is None:
            raise AssertionError('Element members must be set')
        node_refs: set[ElementRef] = {ElementRef('node', member.id) for member in chain(next_members, prev_members)}

        element_state = self.element_state
        bbox_points = self._bbox_points
        bbox_refs = self._bbox_refs
        for node_ref in node_refs:
            entry = element_state.get(node_ref)
            if entry is not None:
                point = entry.current.point
                if point is None:
                    raise AssertionError('Node point must be set')
                bbox_points.append(point)
            else:
                bbox_refs.add(node_ref)

    def _push_bbox_relation_info(self, prev: Element | None, element: Element) -> None:
        """
        Push bbox info for a relation.

        Relation info contains either all members or only changed members.
        """
        next_members = element.members
        prev_members = prev.members if (prev is not None) else ()
        if next_members is None or prev_members is None:
            raise AssertionError('Element members must be set')
        next_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in next_members}
        prev_refs: set[ElementRef] = {ElementRef(member.type, member.id) for member in prev_members}
        changed_refs = prev_refs ^ next_refs

        # check for changed tags or any relation members
        full_diff: cython.char = (
            (prev is None)
            or (prev.tags != element.tags)  #
            or any(ref.type == 'relation' for ref in changed_refs)
        )

        diff_refs = (prev_refs | next_refs) if full_diff else (changed_refs)
        element_state = self.element_state
        bbox_points = self._bbox_points
        bbox_refs = self._bbox_refs
        for member_ref in diff_refs:
            member_type = member_ref.type

            if member_type == 'node':
                entry = element_state.get(member_ref)
                if entry is not None:
                    point = entry.current.point
                    if point is None:
                        raise AssertionError('Node point must be set')
                    bbox_points.append(point)
                else:
                    bbox_refs.add(member_ref)

            elif member_type == 'way':
                entry = element_state.get(member_ref)
                if entry is None:
                    bbox_refs.add(member_ref)
                    continue

                members = entry.current.members
                if members is None:
                    raise AssertionError('Way members must be set')

                for node_member in members:
                    node_ref = ElementRef('node', node_member.id)
                    entry = element_state.get(node_ref)
                    if entry is not None:
                        point = entry.current.point
                        if point is None:
                            raise AssertionError('Node point must be set')
                        bbox_points.append(point)
                    else:
                        bbox_refs.add(node_ref)

    async def _preload_changeset(self) -> None:
        """
        Preload changeset state from the database.
        """
        # currently, enforce single changeset updates
        changeset_ids: set[int] = {element.changeset_id for element, _ in self._elements}
        if len(changeset_ids) > 1:
            raise_for().diff_multiple_changesets()
        changeset_id = next(iter(changeset_ids))

        with options_context(joinedload(Changeset.user).load_only(User.roles)):
            self.changeset = changeset = await ChangesetQuery.find_by_id(changeset_id)

        if changeset is None:
            raise_for().changeset_not_found(changeset_id)
        if changeset.user_id != auth_user(required=True).id:
            raise_for().changeset_access_denied()
        if changeset.closed_at is not None:
            raise_for().changeset_already_closed(changeset_id, changeset.closed_at)

    def _update_changeset_size(self) -> None:
        """
        Update and validate changeset size.
        """
        changeset = self.changeset
        if changeset is None:
            raise AssertionError('Changeset must be set')
        new_size = changeset.size + len(self.apply_elements)
        logging.debug('Optimistic increasing changeset %d size to %d', changeset.id, new_size)
        if not changeset.set_size(new_size):
            raise_for().changeset_too_big(new_size)

    async def _update_changeset_bounds(self) -> None:
        """
        Update changeset bounds using the collected bbox info.
        """
        bbox_points = self._bbox_points
        bbox_refs = self._bbox_refs

        if bbox_refs:
            logging.debug('Optimistic loading %d bbox elements', len(bbox_refs))
            elements = await ElementQuery.get_by_refs(
                bbox_refs,
                at_sequence_id=self.at_sequence_id,
                recurse_ways=True,
                limit=None,
            )
            for element in elements:
                point = element.point
                if point is not None:
                    bbox_points.append(point)
                elif element.type == 'node':
                    versioned_ref = VersionedElementRef('node', element.id, element.version)
                    logging.warning('Node %s is missing coordinates', versioned_ref)

        if not bbox_points:
            return

        changeset = self.changeset
        if changeset is None:
            raise AssertionError('Changeset must be set')

        changeset.bounds = new_bounds = change_bounds(changeset.bounds, bbox_points)

        changeset_union_bounds = changeset.union_bounds
        new_polygons = [cb.bounds for cb in new_bounds]
        if changeset_union_bounds is not None:
            new_polygons.append(changeset_union_bounds)
        changeset.union_bounds = box(*multipolygons(new_polygons).bounds)
