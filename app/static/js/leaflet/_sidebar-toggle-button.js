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
        if (!sidebar) console.error("Sidebar", className, "not found")
        const sidebarCloseButton = sidebar.querySelector(".btn-close")

        // Create container
        const container = document.createElement("div")
        container.className = `leaflet-control ${className}`

        // Create button and tooltip
        const buttonText = i18next.t(tooltipTitle)
        const button = document.createElement("button")
        button.className = "control-button"
        button.ariaLabel = buttonText
        button.innerHTML = `<span class='icon ${className}'></span>`

        const tooltip = new Tooltip(button, {
            title: buttonText,
            placement: "left",
        })

        // Add button to container
        container.appendChild(button)

        // Close sidebar on button click
        const onCloseClick = () => {
            if (button.classList.contains("active")) {
                button.dispatchEvent(new Event("click"))
            }
        }

        // On input checked, toggle sidebar visibility and invalidate map size
        const onButtonClick = () => {
            console.debug("toggleLeafletSidebar", className)

            // TODO: unselect other buttons
            button.blur() // lose focus

            const isActive = button.classList.toggle("active")
            sidebar.classList.toggle("d-none", !isActive)
            map.invalidateSize(false)
        }

        // Listen for events
        sidebarCloseButton.addEventListener("click", onCloseClick)
        button.addEventListener("click", onButtonClick)

        control.sidebar = sidebar
        control.button = button
        control.tooltip = tooltip

        return container
    }

    return control
}
