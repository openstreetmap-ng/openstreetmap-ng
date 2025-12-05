import { routerNavigateStrict } from "@index/router"
import { Tooltip } from "bootstrap"
import i18next from "i18next"
import type { IControl, Map as MaplibreMap } from "maplibre-gl"

export const NEW_NOTE_MIN_ZOOM = 12

const newNoteContainers: HTMLDivElement[] = []

export class NewNoteControl implements IControl {
    public _container: HTMLElement

    public onAdd(map: MaplibreMap) {
        const container = document.createElement("div")
        container.className = "maplibregl-ctrl maplibregl-ctrl-group new-note"

        // Create a button and a tooltip
        const buttonText = i18next.t("javascripts.site.createnote_tooltip")
        const button = document.createElement("button")
        button.type = "button"
        button.className = "control-btn"
        button.ariaLabel = buttonText
        const icon = document.createElement("img")
        icon.className = "icon new-note"
        icon.src = "/static/img/leaflet/_generated/new-note.webp"
        button.appendChild(icon)
        container.appendChild(button)

        new Tooltip(button, {
            title: buttonText,
            placement: "left",
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

        /** On map zoom, change button availability */
        const updateState = () => {
            const zoom = map.getZoom()
            if (zoom < NEW_NOTE_MIN_ZOOM) {
                if (!button.disabled) {
                    button.blur()
                    button.disabled = true
                    Tooltip.getInstance(button).setContent({
                        ".tooltip-inner": i18next.t(
                            "javascripts.site.createnote_disabled_tooltip",
                        ),
                    })
                }
            } else if (button.disabled) {
                button.disabled = false
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.createnote_tooltip"),
                })
            }
        }

        // Listen for events
        map.on("zoomend", updateState)
        // Initial update to set button states
        updateState()
        newNoteContainers.push(container)
        this._container = container
        return container
    }

    public onRemove() {
        // Not implemented
    }
}

/** Set availability of the new note button */
export const setNewNoteButtonState = (active: boolean) => {
    console.debug(
        "setNewNoteButtonState",
        active,
        "on",
        newNoteContainers.length,
        "containers",
    )
    for (const container of newNoteContainers) {
        const button = container.querySelector(".control-btn")
        button.classList.toggle("active", active)
    }
}
