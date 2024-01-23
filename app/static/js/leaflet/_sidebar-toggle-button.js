import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"

/**
 * Create a sidebar toggle button
 * @param {string} className Class name of the sidebar
 * @param {string} tooltipTitle Title of the tooltip
 * @returns {L.Control} Sidebar toggle button
 */
export const getSidebarToggleButton = (className, tooltipTitle) => {
    const control = new L.Control()

    control.onAdd = (map) => {
        // Find corresponding sidebar
        const sidebar = document.querySelector(`.leaflet-sidebar.${className}`)
        if (!sidebar) console.error(`Sidebar ${className} not found`)

        // Create container
        const container = document.createElement("div")

        // Create button and tooltip
        const input = document.createElement("input")
        input.type = "radio"
        input.name = "sidebar-toggle"
        input.id = `sidebar-toggle-${className}`
        input.className = "btn-check"

        // Always deselect the input on load/reload
        input.autocomplete = "off"

        const label = document.createElement("label")
        label.className = "control-button"
        label.innerHTML = `<span class='icon ${className}'></span>`
        label.htmlFor = input.id

        const tooltip = new Tooltip(label, {
            title: i18next.t(tooltipTitle),
            placement: "left",
        })

        // Add button to container
        container.appendChild(input)
        container.appendChild(label)

        // On input checked, toggle sidebar visibility and invalidate map size
        const onChange = () => {
            sidebar.classList.toggle("d-none", !input.checked)
            map.invalidateSize({ pan: false }) // TODO: skipping animation, seems unnecessary
        }

        // Listen for events
        input.addEventListener("change", onChange)

        control.sidebar = sidebar
        control.input = input
        control.label = label
        control.tooltip = tooltip

        return container
    }

    return control
}
