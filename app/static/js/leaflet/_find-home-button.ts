import * as L from "leaflet"
import type { LonLat } from "./_map-utils"
import { getMarkerIcon } from "./_utils"

/** Configure the find home button */
export const configureFindHomeButton = (map: L.Map, button: HTMLButtonElement, { lon, lat }: LonLat): void => {
    const latLng = L.latLng(lat, lon)
    let marker: L.Marker | null = null

    // On click, create a marker and zoom to it
    button.addEventListener("click", () => {
        console.debug("onFindHomeButtonClick")

        if (!marker) {
            marker = L.marker(latLng, {
                icon: getMarkerIcon("blue-home", true), // TODO: revise icon
                keyboard: false,
                interactive: false,
            })
            map.addLayer(marker)
        }

        // Home zoom defaults to 15
        map.setView(latLng, 15)
    })
}
