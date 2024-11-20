import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import { routerNavigateStrict } from "../index/_router"
import { newNoteMinZoom } from "./_context-menu"

const newNoteContainers: HTMLDivElement[] = []

export const getNewNoteControl = () => {
    let controlMap: L.Map | null = null
    let controlContainer: HTMLDivElement | null = null

    /** On zoomend, disable/enable button */
    const onZoomEnd = (): void => {
        const button = controlContainer.querySelector("button")

        // Enable/disable buttons based on current zoom level
        const currentZoom = controlMap.getZoom()
        if (currentZoom < newNoteMinZoom) {
            if (!button.disabled) {
                button.blur()
                button.disabled = true
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.createnote_disabled_tooltip"),
                })
            }
        } else {
            // biome-ignore lint/style/useCollapsedElseIf: Readability
            if (button.disabled) {
                button.disabled = false
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.createnote_tooltip"),
                })
            }
        }
    }

    const control = new L.Control()
    control.onAdd = (map: L.Map): HTMLElement => {
        if (controlMap) {
            console.error("NewNoteControl has already been added to the map")
            return
        }
        controlMap = map

        // Create container
        controlContainer = document.createElement("div")
        controlContainer.className = "leaflet-control new-note"

        // Create a button and a tooltip
        const buttonText = i18next.t("javascripts.site.createnote_tooltip")
        const button = document.createElement("button")
        button.className = "control-button"
        button.ariaLabel = buttonText
        const icon = document.createElement("img")
        icon.className = "icon new-note"
        icon.src = "/static/img/leaflet/_generated/new-note.webp"
        button.appendChild(icon)
        controlContainer.appendChild(button)

        new Tooltip(button, {
            title: buttonText,
            placement: "left",
            // TODO: check RTL support, also with leaflet options
        })

        // On button click, navigate to the new note page
        button.addEventListener("click", () => {
            const isActive = button.classList.contains("active")
            if (!isActive) {
                routerNavigateStrict("/note/new")
            } else {
                routerNavigateStrict("/")
            }
            button.blur() // lose focus
        })

        // Listen for events
        map.addEventListener("zoomend", onZoomEnd)
        // Initial update to set button states
        onZoomEnd()

        newNoteContainers.push(controlContainer)
        return controlContainer
    }

    return control
}

/** Set availability of the new note button */
export const setNewNoteButtonState = (active: boolean): void => {
    console.debug("setNewNoteButtonState", active, "on", newNoteContainers.length, "containers")
    for (const container of newNoteContainers) {
        const button = container.querySelector(".control-button")
        button.classList.toggle("active", active)
    }
}
