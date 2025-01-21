import { Tooltip } from "bootstrap"
import i18next from "i18next"
import type { IControl, Map as MaplibreMap } from "maplibre-gl"

const sidebarToggleContainers: HTMLElement[] = []

export class SidebarToggleControl implements IControl {
    protected sidebar?: HTMLElement
    private readonly _className: string
    private readonly _tooltipTitle: string

    public constructor(className: string, tooltipTitle: string) {
        this._className = className
        this._tooltipTitle = tooltipTitle
    }

    public onAdd(map: MaplibreMap): HTMLElement {
        // Find corresponding sidebar
        const sidebar = document.querySelector(`div.leaflet-sidebar.${this._className}`)
        if (!sidebar) console.error("Sidebar", this._className, "not found")
        this.sidebar = sidebar

        // Create container
        const container = document.createElement("div")
        container.className = `maplibregl-ctrl maplibregl-ctrl-group ${this._className}`

        // Create button and tooltip
        const buttonText = i18next.t(this._tooltipTitle)
        const button = document.createElement("button")
        button.type = "button"
        button.className = "control-button"
        button.ariaLabel = buttonText
        const icon = document.createElement("img")
        icon.className = `icon ${this._className}`
        icon.src = `/static/img/leaflet/_generated/${this._className}.webp`
        button.appendChild(icon)
        container.appendChild(button)

        // noinspection ObjectAllocationIgnored
        new Tooltip(button, {
            title: buttonText,
            placement: "left",
        })

        // On click, toggle sidebar visibility and invalidate map size
        button.addEventListener("click", () => {
            console.debug("onSidebarToggleButtonClick", this._className)

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
            map.resize()
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

    public onRemove(_: MaplibreMap): void {
        // Do nothing
    }
}
