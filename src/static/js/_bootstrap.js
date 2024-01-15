import { Tooltip } from "bootstrap"

// Initialize tooltips
for (const element of document.querySelectorAll("[data-bs-toggle=tooltip]")) {
    new Tooltip(element)
}
