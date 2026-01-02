import type { Collapse, Dropdown, Modal, Offcanvas } from "bootstrap"

declare global {
  interface HTMLElementEventMap {
    "show.bs.modal": Modal.Event
    "shown.bs.modal": Modal.Event
    "hide.bs.modal": Modal.Event
    "hidden.bs.modal": Modal.Event
    "hidePrevented.bs.modal": Modal.Event

    "show.bs.dropdown": Dropdown.Event
    "shown.bs.dropdown": Dropdown.Event
    "hide.bs.dropdown": Dropdown.Event
    "hidden.bs.dropdown": Dropdown.Event

    "show.bs.collapse": Collapse.Event
    "shown.bs.collapse": Collapse.Event
    "hide.bs.collapse": Collapse.Event
    "hidden.bs.collapse": Collapse.Event

    "show.bs.offcanvas": Offcanvas.Event
    "shown.bs.offcanvas": Offcanvas.Event
    "hide.bs.offcanvas": Offcanvas.Event
    "hidden.bs.offcanvas": Offcanvas.Event
    "hidePrevented.bs.offcanvas": Offcanvas.Event
  }
}
