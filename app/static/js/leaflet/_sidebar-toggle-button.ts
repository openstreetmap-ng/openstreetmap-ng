import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"

export interface SidebarToggleControl extends L.Control {
    sidebar?: HTMLElement
}

const sidebarToggleContainers: HTMLElement[] = []

/** Create a sidebar toggle button */
export const getSidebarToggleButton = (className: string, tooltipTitle: string): SidebarToggleControl => {
    const control = new L.Control() as SidebarToggleControl

    control.onAdd = (map: L.Map): HTMLElement => {
        // Find corresponding sidebar
        const sidebar = document.querySelector(`div.leaflet-sidebar.${className}`)
        if (!sidebar) console.error("Sidebar", className, "not found")
        control.sidebar = sidebar

        // Create container
        const container = document.createElement("div")
        container.className = `leaflet-control ${className}`

        // Create button and tooltip
        const buttonText = i18next.t(tooltipTitle)
        const button = document.createElement("button")
        button.className = "control-button"
        button.ariaLabel = buttonText
        button.innerHTML = `<span class='icon ${className}'></span>`
        container.appendChild(button)

        new Tooltip(button, {
            title: buttonText,
            placement: "left",
        })

        // On click, toggle sidebar visibility and invalidate map size
        button.addEventListener("click", () => {
            console.debug("onSidebarToggleButtonClick", className)

            // Unselect other buttons
            for (const otherContainer of sidebarToggleContainers) {
                if (otherContainer === container) continue
                const otherButton = otherContainer.querySelector(".control-button")
                if (otherButton.classList.contains("active")) {
                    console.debug("Unselecting sidebar toggle button", otherButton)
                    otherButton.dispatchEvent(new Event("click"))
                }
            }

            // Lose focus
            button.blur()

            const isActive = button.classList.toggle("active")
            sidebar.classList.toggle("d-none", !isActive)
            map.invalidateSize(false)
        })

        // On sidebar close button, trigger the sidebar toggle button
        const sidebarCloseButton = sidebar.querySelector(".sidebar-close-btn")
        sidebarCloseButton.addEventListener("click", () => {
            if (button.classList.contains("active")) {
                button.dispatchEvent(new Event("click"))
            }
        })

        sidebarToggleContainers.push(container)
        return container
    }

    return control
}
