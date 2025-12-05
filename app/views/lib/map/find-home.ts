import { type Map as MaplibreMap, Marker } from "maplibre-gl"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "./marker"
import type { LonLat } from "./state"

/** Configure the find home button */
export const configureFindHomeButton = (
    map: MaplibreMap,
    button: HTMLButtonElement,
    { lon, lat }: LonLat,
) => {
    let marker: Marker | null = null

    // On click, create a marker and zoom to it
    button.addEventListener("click", () => {
        console.debug("onFindHomeButtonClick")
        if (!marker) {
            marker = new Marker({
                anchor: MARKER_ICON_ANCHOR,
                // @ts-expect-error
                element: getMarkerIconElement("blue-home", true),
            })
                .setLngLat([lon, lat])
                .addTo(map)
        }
        map.flyTo({ center: [lon, lat] })
    })
}
