import logging
from collections import defaultdict
from collections.abc import Sequence
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
from app.models.db.user import User
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.models.osmchange_action import OSMChangeAction
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery


@dataclass(slots=True)
class ElementStateEntry:
    remote: Element | None
    local: Element | None


@dataclass(slots=True)
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

    _bbox_info: set[Point | ElementRef]
    """
    Changeset bounding box info, set of points and element refs.
    """

    def __init__(self, elements: Sequence[Element]) -> None:
        self.at_sequence_id = None
        self.apply_elements = []
        self._elements = tuple((element, ElementRef(element.type, element.id)) for element in elements)
        self.element_state = {}
        self._elements_parents_refs = {}
        self._elements_check_members_remote = []
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
            entry: ElementStateEntry | None
            prev: Element | None
            if element.version == 1:
                action = 'create'

                if element.id >= 0:
                    raise_for().diff_create_bad_id(element)
                if element_ref in self.element_state:
                    raise AssertionError(f'Element {element_ref!r} already exists in the element state')

                entry = ElementStateEntry(None, None)
                self.element_state[element_ref] = entry
                prev = None
            else:
                action = 'modify' if element.visible else 'delete'
                entry = self.element_state.get(element_ref)
                if entry is None:
                    raise_for().element_not_found(element_ref)

                prev = entry.local if (entry.local is not None) else entry.remote
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
            entry.local = element

        self._update_changeset_size()

        async with create_task_group() as tg:
            tg.start_soon(self._update_changeset_bounds)
            tg.start_soon(self._check_members_remote)

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
        elements = await ElementQuery.get_by_refs(
            refs,
            at_sequence_id=self.at_sequence_id,
            limit=refs_len,
        )

        # check if all elements exist
        if len(elements) != refs_len:
            for element in elements:
                refs.remove(ElementRef(element.type, element.id))
            element_ref = next(iter(refs))
            raise_for().element_not_found(element_ref)

        # if they do, push them to the element state
        self.element_state = {
            ElementRef(element.type, element.id): ElementStateEntry(element, None)  #
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
            if entry is None:
                notfound.add(member_ref)
                continue
            member = entry.local if (entry.local is not None) else entry.remote
            if member is None and member_ref == parent_ref:
                member = parent
            if not member.visible:
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
        hidden_ref = hidden_refs[0] if hidden_refs else None
        if hidden_ref is None:
            return

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
            entry = element_state.get(node_ref)
            if entry is not None:
                node = entry.local if (entry.local is not None) else entry.remote
                bbox_info.add(node.point)
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
                entry = element_state.get(member_ref)
                if entry is not None:
                    node = entry.local if (entry.local is not None) else entry.remote
                    bbox_info.add(node.point)
                else:
                    bbox_info.add(member_ref)

            elif member_type == 'way':
                ways = element_state.get(member_ref)
                if ways is None:
                    bbox_info.add(member_ref)
                    continue

                for node_member in ways[-1].members:
                    node_ref = ElementRef('node', node_member.id)
                    entry = element_state.get(node_ref)
                    if entry is not None:
                        node = entry.local if (entry.local is not None) else entry.remote
                        bbox_info.add(node.point)
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

        with options_context(joinedload(Changeset.user).load_only(User.roles)):
            changeset = await ChangesetQuery.get_by_id(changeset_id)

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
            elements = await ElementQuery.get_by_refs(
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
