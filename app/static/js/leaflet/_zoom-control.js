import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"

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
            zoomOutButton.blur()
            zoomOutButton.disabled = true
        } else {
            zoomOutButton.disabled = false
        }

        if (currentZoom >= maxZoom) {
            zoomInButton.blur()
            zoomInButton.disabled = true
        } else {
            zoomInButton.disabled = false
        }
    }

    control.onAdd = (map) => {
        if (control.map) console.error("ZoomControl has already been added to a map")

        // Create container
        const container = document.createElement("div")
        container.className = "leaflet-control zoom"

        // Create buttons and tooltips
        const zoomInText = i18next.t("javascripts.map.zoom.in")
        const zoomInButton = document.createElement("button")
        zoomInButton.className = "control-button"
        zoomInButton.ariaLabel = zoomInText
        zoomInButton.innerHTML = "<span class='icon zoom-in'></span>"

        new Tooltip(zoomInButton, {
            title: zoomInText,
            placement: "left",
        })

        const zoomOutText = i18next.t("javascripts.map.zoom.out")
        const zoomOutButton = document.createElement("button")
        zoomOutButton.className = "control-button"
        zoomOutButton.ariaLabel = zoomOutText
        zoomOutButton.innerHTML = "<span class='icon zoom-out'></span>"

        new Tooltip(zoomOutButton, {
            title: zoomOutText,
            placement: "left",
        })

        // Add buttons to container
        container.appendChild(zoomInButton)
        container.appendChild(zoomOutButton)

        control.zoomInButton = zoomInButton
        control.zoomOutButton = zoomOutButton
        control.map = map

        const onZoomInButtonClick = () => map.zoomIn(1)
        const onZoomOutButtonClick = () => map.zoomOut(1)

        // Listen for events
        map.addEventListener("zoomend zoomlevelschange", onMapZoomChange)
        zoomInButton.addEventListener("click", onZoomInButtonClick)
        zoomOutButton.addEventListener("click", onZoomOutButtonClick)

        // Initial update to set button states
        onMapZoomChange()

        return container
    }

    return control
}
