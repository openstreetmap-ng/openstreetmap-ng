import * as L from "leaflet"
import { getGeoUri, getMapEmbedHtml, getMapShortUrl, getMapUrl } from "../_utils.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"

export const getShareSidebarToggleButton = (options) => {
    const control = getSidebarToggleButton(options, "share", "javascripts.share.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const input = control.input

        const markerCheckbox = sidebar.querySelector(".marker-checkbox")
        const linkRadioInput = sidebar.querySelector(".link-button")
        const linkInput = sidebar.querySelector(".link-input")
        const shortLinkRadioInput = sidebar.querySelector(".short-link-button")
        const shortLinkInput = sidebar.querySelector(".short-link-input")
        const embedRadioInput = sidebar.querySelector(".embed-button")
        const embedInput = sidebar.querySelector(".embed-input")
        const geoUriLink = sidebar.querySelector(".geo-uri-link")

        // Null values until the marker/locationFilter is initialized
        let marker = null
        let locationFilter = null

        const updateLinks = () => {
            const showMarker = markerCheckbox.checked

            if (linkRadioInput.checked) {
                const link = getMapUrl(map, showMarker)
                linkInput.value = link
            } else if (shortLinkRadioInput.checked) {
                const shortLink = getMapShortUrl(map, showMarker)
                shortLinkInput.value = shortLink
            } else if (embedRadioInput.checked) {
                const markerLatLng = showMarker ? marker.getLatLng() : null
                const embed = getMapEmbedHtml(map, markerLatLng)
                embedInput.value = embed
            }
        }

        const updateGeoUri = () => {
            const geoUri = getGeoUri(map)
            geoUriLink.href = geoUri
            geoUriLink.textContent = geoUri
        }

        // On map move, update marker position if marker is enabled
        const onMapMove = () => {
            if (markerCheckbox.checked) {
                marker.setLatLng(map.getCenter())
            }
        }

        // On map move, update sidebar data
        const onMapMoveEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            updateLinks()
            updateGeoUri()
        }

        // On marker checkbox change, display/hide the marker
        const onMarkerCheckboxChange = () => {
            if (markerCheckbox.checked) {
                if (!marker) {
                    marker = L.marker(map.getCenter(), { draggable: true })
                    marker.on("dragend", onMarkerDragEnd)
                } else {
                    marker.setLatLng(map.getCenter())
                }

                // Display marker and chance zoom mode to center
                map.addLayer(marker)
                map.options.scrollWheelZoom = map.options.doubleClickZoom = "center"
            } else {
                // Hide marker and reset zoom mode
                map.removeLayer(marker)
                map.options.scrollWheelZoom = map.options.doubleClickZoom = true
            }
        }

        // On marker drag end, center map to marker
        const onMarkerDragEnd = () => {
            map.removeEventListener("move", onMapMove)
            map.panTo(marker.getLatLng())
            map.addOneTimeEventListener("moveend", () => {
                map.addEventListener("move", onMapMove)
            })
        }

        // Listen for events
        map.addEventListener("move", onMapMove)
        map.addEventListener("moveend", onMapMoveEnd)
        markerCheckbox.addEventListener("change", onMarkerCheckboxChange)
        linkRadioInput.addEventListener("change", () => {
            if (linkRadioInput.checked) updateLinks()
        })
        shortLinkRadioInput.addEventListener("change", () => {
            if (shortLinkRadioInput.checked) updateLinks()
        })
        embedRadioInput.addEventListener("change", () => {
            if (embedRadioInput.checked) updateLinks()
        })

        // TODO: deselect checkbox
        // TODO: on show panel

        return container
    }
}
