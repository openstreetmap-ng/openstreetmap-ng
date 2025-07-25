import { Alert, Popover, Tooltip } from "bootstrap"

// Initialize bootstrap components

// https://getbootstrap.com/docs/5.3/components/tooltips/
for (const element of document.querySelectorAll("[data-bs-toggle=tooltip]")) {
    new Tooltip(element)
}

// https://getbootstrap.com/docs/5.3/components/alerts/
for (const element of document.querySelectorAll(".alert")) {
    new Alert(element)
}

// https://getbootstrap.com/docs/5.3/components/popovers/
for (const element of document.querySelectorAll("[data-bs-toggle=popover]")) {
    new Popover(element)
}
