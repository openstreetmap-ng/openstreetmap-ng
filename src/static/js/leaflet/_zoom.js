import { Tooltip } from "bootstrap"
import * as L from "leaflet"

// TODO: is that even necessary?

export const getZoomControl = (options) => {
    const control = L.control(options)

    // On zoom change, disable/enable specific buttons
    const onZoomChange = () => {
        const currentZoom = control.map.getZoom()
        const minZoom = control.map.getMinZoom()
        const maxZoom = control.map.getMaxZoom()

        // Enable/disable buttons based on current zoom level
        if (currentZoom <= minZoom) {
            control.zoomOutButton.disabled = true
        } else {
            control.zoomOutButton.disabled = false
        }

        if (currentZoom >= maxZoom) {
            control.zoomInButton.disabled = true
        } else {
            control.zoomInButton.disabled = false
        }
    }

    control.onAdd = (map) => {
        if (control.map) console.error("ZoomControl has already been added to a map")

        // Create container
        const container = document.createElement("div")

        // Create buttons and tooltips
        const zoomInButton = document.createElement("button")
        zoomInButton.className = "control-button"
        zoomInButton.innerHTML = "<span class='icon zoomin'></span>"

        const zoomInTooltip = Tooltip.getOrCreateInstance(zoomInButton, {
            title: I18n.t("javascripts.map.zoom.in"),
            placement: "left",
        })

        const zoomOutButton = document.createElement("button")
        zoomOutButton.className = "control-button"
        zoomOutButton.innerHTML = "<span class='icon zoomout'></span>"

        const zoomOutTooltip = Tooltip.getOrCreateInstance(zoomOutButton, {
            title: I18n.t("javascripts.map.zoom.out"),
            placement: "left",
        })

        // Add buttons to container
        container.appendChild(zoomInButton)
        container.appendChild(zoomOutButton)

        const onZoomIn = (e) => {
            map.zoomIn(e.shiftKey ? 3 : 1)
        }

        const onZoomOut = (e) => {
            map.zoomOut(e.shiftKey ? 3 : 1)
        }

        control.zoomInButton = zoomInButton
        control.zoomInTooltip = zoomInTooltip
        control.zoomOutButton = zoomOutButton
        control.zoomOutTooltip = zoomOutTooltip
        control.map = map

        // Listen for events
        zoomInButton.addEventListener("click", onZoomIn)
        zoomOutButton.addEventListener("click", onZoomOut)
        map.addEventListener("zoomend zoomlevelschange", onZoomChange)

        // Initial update to set button states
        onZoomChange()

        return container
    }

    return control
}
