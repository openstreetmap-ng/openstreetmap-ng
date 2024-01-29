import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import { queryFeaturesMinZoom } from "./_context-menu.js"

export const getQueryFeaturesControl = () => {
    const control = new L.Control()

    // On zoomend, disable/enable button
    const onZoomEnd = () => {
        const map = control.map
        const button = control.button
        const tooltip = control.tooltip

        const currentZoom = map.getZoom()

        // Enable/disable buttons based on current zoom level
        if (currentZoom < queryFeaturesMinZoom) {
            if (!button.disabled) {
                button.disabled = true
                tooltip.setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.queryfeature_disabled_tooltip"),
                })
            }
        } else {
            // biome-ignore lint/style/useCollapsedElseIf: Readability
            if (button.disabled) {
                button.disabled = false
                tooltip.setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.queryfeature_tooltip"),
                })
            }
        }
    }

    control.onAdd = (map) => {
        if (control.map) console.error("QueryFeaturesControl has already been added to a map")

        // Create container
        const container = document.createElement("div")

        // Create a button and a tooltip
        const button = document.createElement("button")
        button.className = "control-button"
        button.innerHTML = "<span class='icon query'></span>"

        const tooltip = new Tooltip(button, {
            title: i18next.t("javascripts.site.queryfeature_tooltip"),
            placement: "left",
            // TODO: check RTL support, also with leaflet options
        })

        control.button = button
        control.tooltip = tooltip
        control.map = map

        // TODO: active state, handle click on map, precision!

        // Listen for events
        map.addEventListener("zoomend", onZoomEnd)

        // Initial update to set button states
        onZoomEnd()

        return container
    }

    return control
}
