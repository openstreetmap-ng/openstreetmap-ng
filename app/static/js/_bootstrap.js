import { Alert, Tooltip } from "bootstrap"

// Initialize tooltips
// https://getbootstrap.com/docs/5.3/components/tooltips/
for (const element of document.querySelectorAll("[data-bs-toggle=tooltip]")) {
    new Tooltip(element)
}

// Initialize alerts
// https://getbootstrap.com/docs/5.3/components/alerts/
for (const element of document.querySelectorAll(".alert")) {
    new Alert(element)
}
