import { type Map as MaplibreMap, Marker } from "maplibre-gl"
import type { LonLat } from "./map-utils"
import { getMarkerIconElement, markerIconAnchor } from "./utils"

/** Configure the find home button */
export const configureFindHomeButton = (
    map: MaplibreMap,
    button: HTMLButtonElement,
    { lon, lat }: LonLat,
): void => {
    let marker: Marker | null = null

    // On click, create a marker and zoom to it
    button.addEventListener("click", () => {
        console.debug("onFindHomeButtonClick")
        if (!marker) {
            marker = new Marker({
                anchor: markerIconAnchor,
                element: getMarkerIconElement("blue-home", true),
            })
                .setLngLat([lon, lat])
                .addTo(map)
        }
        map.flyTo({ center: [lon, lat] })
    })
}
