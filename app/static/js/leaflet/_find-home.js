import * as L from "leaflet"
import { homePoint } from "../_params.js"
import { getMarkerIcon } from "./_utils.js"

/**
 * Configure the find home button
 * @param {L.Map} map Leaflet map to configure the button for
 * @param {HTMLElement} button The button element
 * @returns {void}
 */
export const configureFindHomeButton = (map, button) => {
    const [lon, lat] = JSON.parse(homePoint)
    const latLng = L.latLng(lat, lon)

    let marker = null

    // On click, create a marker and zoom to it
    const onClick = () => {
        if (!marker) {
            marker = L.marker(latLng, {
                icon: getMarkerIcon("blue-home", true),
                keyboard: false,
                interactive: false,
            })
            map.addLayer(marker)
        }

        // Home zoom defaults to 15
        map.setView(latLng, 15)
    }

    // Listen for events
    button.addEventListener("click", onClick)
}
