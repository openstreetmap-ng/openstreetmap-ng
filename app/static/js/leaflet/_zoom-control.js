import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"

// TODO: is that even necessary?
const shiftAccel = 3

export const getZoomControl = () => {
    const control = new L.Control()

    // On zoom change, disable/enable specific buttons
    const onMapZoomChange = () => {
        const map = control.map
        const zoomInButton = control.zoomInButton
        const zoomOutButton = control.zoomOutButton

        const currentZoom = map.getZoom()
        const minZoom = map.getMinZoom()
        const maxZoom = map.getMaxZoom()

        // Enable/disable buttons based on current zoom level
        if (currentZoom <= minZoom) {
            zoomOutButton.disabled = true
        } else {
            zoomOutButton.disabled = false
        }

        if (currentZoom >= maxZoom) {
            zoomInButton.disabled = true
        } else {
            zoomInButton.disabled = false
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

        const zoomInTooltip = new Tooltip(zoomInButton, {
            title: i18next.t("javascripts.map.zoom.in"),
            placement: "left",
        })

        const zoomOutButton = document.createElement("button")
        zoomOutButton.className = "control-button"
        zoomOutButton.innerHTML = "<span class='icon zoomout'></span>"

        const zoomOutTooltip = new Tooltip(zoomOutButton, {
            title: i18next.t("javascripts.map.zoom.out"),
            placement: "left",
        })

        // Add buttons to container
        container.appendChild(zoomInButton)
        container.appendChild(zoomOutButton)

        const onZoomInButtonClick = (e) => {
            map.zoomIn(e.shiftKey ? shiftAccel : 1)
        }

        const onZoomOutButtonClick = (e) => {
            map.zoomOut(e.shiftKey ? shiftAccel : 1)
        }

        control.zoomInButton = zoomInButton
        control.zoomInTooltip = zoomInTooltip
        control.zoomOutButton = zoomOutButton
        control.zoomOutTooltip = zoomOutTooltip
        control.map = map

        // Listen for events
        zoomInButton.addEventListener("click", onZoomInButtonClick)
        zoomOutButton.addEventListener("click", onZoomOutButtonClick)
        map.addEventListener("zoomend zoomlevelschange", onMapZoomChange)

        // Initial update to set button states
        onMapZoomChange()

        return container
    }

    return control
}
