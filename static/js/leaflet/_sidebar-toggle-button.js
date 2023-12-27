import { Tooltip } from "bootstrap"
import * as L from "leaflet"

export const getSidebarToggleButton = (options, className, tooltipTitle) => {
    const control = L.control(options)

    control.onAdd = () => {
        // Find corresponding sidebar
        const sidebar = document.querySelector(`.sidebar.leaflet-sidebar.${className}`)
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

        const tooltip = Tooltip.getOrCreateInstance(label, {
            title: I18n.t(tooltipTitle),
            placement: "left",
        })

        // Add button to container
        container.appendChild(input)
        container.appendChild(label)

        // Listen for events
        const onChange = () => {
            if (input.checked) {
                sidebar.classList.remove("d-none")
            } else {
                sidebar.classList.add("d-none")
            }
        }

        input.addEventListener("change", onChange)

        control.sidebar = sidebar
        control.input = input
        control.label = label
        control.tooltip = tooltip

        return container
    }

    return control
}
