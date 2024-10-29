import * as L from "leaflet"
import { getMarkerIcon } from "./_utils"

/** Configure the find home button */
export const configureFindHomeButton = (map: L.Map, button: HTMLButtonElement, homePoint: [number, number]): void => {
    const latLng = L.latLng(homePoint)
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
