import * as L from "leaflet"

export const getZoomControl = (options) => {
    const control = L.control(options)

    // On zoom change, disable/enable specific buttons
    const onZoomChange = () => {
        const currentZoom = control.map.getZoom()
        const minZoom = control.map.getMinZoom()
        const maxZoom = control.map.getMaxZoom()

        // Enable/disable buttons based on current zoom level
        if (currentZoom === minZoom) {
            control.zoomOutButton.classList.add("disabled")
        } else {
            control.zoomOutButton.classList.remove("disabled")
        }

        if (currentZoom === maxZoom) {
            control.zoomInButton.classList.add("disabled")
        } else {
            control.zoomInButton.classList.remove("disabled")
        }
    }

    control.onAdd = (map) => {
        // Create container
        const container = document.createElement("div")

        // Create buttons
        const zoomInButton = document.createElement("button")
        zoomInButton.className = "control-button"
        zoomInButton.title = I18n.t("javascripts.map.zoom.in")
        zoomInButton.innerHTML = "<span class='icon zoomin'></span>"

        const zoomOutButton = document.createElement("button")
        zoomOutButton.className = "control-button"
        zoomOutButton.title = I18n.t("javascripts.map.zoom.out")
        zoomOutButton.innerHTML = "<span class='icon zoomout'></span>"

        // Add buttons to container
        container.appendChild(zoomInButton)
        container.appendChild(zoomOutButton)

        // Listen for events
        const onZoomIn = (e) => {
            map.zoomIn(e.shiftKey ? 3 : 1)
        }

        const onZoomOut = (e) => {
            map.zoomOut(e.shiftKey ? 3 : 1)
        }

        zoomInButton.addEventListener("click", onZoomIn)
        zoomOutButton.addEventListener("click", onZoomOut)
        map.addEventListener("zoomend zoomlevelschange", onZoomChange)

        control.zoomInButton = zoomInButton
        control.zoomOutButton = zoomOutButton
        control.map = map

        return container
    }

    control.onRemove = (map) => {
        // Remove map event listeners
        map.removeEventListener("zoomend zoomlevelschange", onZoomChange)
    }

    return control
}
