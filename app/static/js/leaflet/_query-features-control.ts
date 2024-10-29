import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import { queryFeaturesMinZoom } from "./_context-menu"

export const getQueryFeaturesControl = () => {
    let controlMap: L.Map | null = null
    let controlContainer: HTMLDivElement | null = null

    /** On zoomend, disable/enable button */
    const onZoomEnd = () => {
        const button = controlContainer.querySelector("button")

        // Enable/disable buttons based on current zoom level
        const currentZoom = controlMap.getZoom()
        if (currentZoom < queryFeaturesMinZoom) {
            if (!button.disabled) {
                button.blur()
                button.disabled = true
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.queryfeature_disabled_tooltip"),
                })
            }
        } else {
            // biome-ignore lint/style/useCollapsedElseIf: Readability
            if (button.disabled) {
                button.disabled = false
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.queryfeature_tooltip"),
                })
            }
        }
    }

    const control = new L.Control()
    control.onAdd = (map: L.Map): HTMLElement => {
        if (controlMap) {
            console.error("QueryFeaturesControl has already been added to the map")
            return
        }
        controlMap = map

        // Create container
        controlContainer = document.createElement("div")
        controlContainer.className = "leaflet-control query-features"

        // Create a button and a tooltip
        const buttonText = i18next.t("javascripts.site.queryfeature_tooltip")
        const button = document.createElement("button")
        button.className = "control-button"
        button.ariaLabel = buttonText
        button.innerHTML = "<span class='icon query-features'></span>"
        controlContainer.appendChild(button)

        new Tooltip(button, {
            title: buttonText,
            placement: "left",
            // TODO: check RTL support, also with leaflet options
        })

        // TODO: active state, handle click on map, precision!

        // Listen for events
        map.addEventListener("zoomend", onZoomEnd)
        // Initial update to set button states
        onZoomEnd()

        return controlContainer
    }

    return control
}
