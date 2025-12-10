import type { Collapse, Dropdown, Modal, Offcanvas } from "bootstrap"

declare global {
    interface HTMLElementEventMap {
        [Modal.Events.show]: Modal.Event
        [Modal.Events.shown]: Modal.Event
        [Modal.Events.hide]: Modal.Event
        [Modal.Events.hidden]: Modal.Event
        [Modal.Events.hidePrevented]: Modal.Event

        [Dropdown.Events.show]: Dropdown.Event
        [Dropdown.Events.shown]: Dropdown.Event
        [Dropdown.Events.hide]: Dropdown.Event
        [Dropdown.Events.hidden]: Dropdown.Event

        [Collapse.Events.show]: Collapse.Event
        [Collapse.Events.shown]: Collapse.Event
        [Collapse.Events.hide]: Collapse.Event
        [Collapse.Events.hidden]: Collapse.Event

        [Offcanvas.Events.show]: Offcanvas.Event
        [Offcanvas.Events.shown]: Offcanvas.Event
        [Offcanvas.Events.hide]: Offcanvas.Event
        [Offcanvas.Events.hidden]: Offcanvas.Event
        [Offcanvas.Events.hidePrevented]: Offcanvas.Event
    }
}
