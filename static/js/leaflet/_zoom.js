import * as L from "leaflet"

const ZoomControl = L.Control.extend({
    options: {
        position: "topright",
    },

    onAdd: function (map) {
        // Create container
        const container = document.createElement("div")
        container.className = "zoom"

        // Create buttons
        const zoomInButton = document.createElement("button")
        zoomInButton.className = "control-button zoomin"
        zoomInButton.title = I18n.t("javascripts.map.zoom.in")
        zoomInButton.innerHTML = "<span class='icon zoomin'></span>"

        const zoomOutButton = document.createElement("button")
        zoomOutButton.className = "control-button zoomout"
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

        map.addEventListener("zoomend zoomlevelschange", this.updateButtonState, this)
        zoomInButton.addEventListener("click", onZoomIn)
        zoomOutButton.addEventListener("click", onZoomOut)

        this.map = map
        this.zoomInButton = zoomInButton
        this.zoomOutButton = zoomOutButton

        return container
    },

    onRemove: function (map) {
        // Remove map event listeners
        map.removeEventListener("zoomend zoomlevelschange", this.updateButtonState, this)
    },

    updateButtonState: function () {
        const disabledClassName = "disabled"
        const currentZoom = this._map.getZoom()
        const minZoom = this._map.getMinZoom()
        const maxZoom = this._map.getMaxZoom()

        // Enable/disable buttons based on current zoom level
        if (currentZoom === minZoom) {
            this._zoomOutButton.classList.add(disabledClassName)
        } else {
            this._zoomOutButton.classList.remove(disabledClassName)
        }

        if (currentZoom === maxZoom) {
            this._zoomInButton.classList.add(disabledClassName)
        } else {
            this._zoomInButton.classList.remove(disabledClassName)
        }
    },
})

export const getZoomControl = (options) => new ZoomControl(options)
