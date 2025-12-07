import { type Map as MaplibreMap, Marker } from "maplibre-gl"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "./marker"
import type { LonLat } from "./state"

export const configureFindHomeButton = (
    map: MaplibreMap,
    button: HTMLButtonElement,
    { lon, lat }: LonLat,
) => {
    // biome-ignore lint/correctness/noUnusedVariables: not implemented
    let marker: Marker | undefined

    // On click, create a marker and zoom to it
    button.addEventListener("click", () => {
        console.debug("onFindHomeButtonClick")
        marker ??= new Marker({
            anchor: MARKER_ICON_ANCHOR,
            // @ts-expect-error
            element: getMarkerIconElement("blue-home", true),
        })
            .setLngLat([lon, lat])
            .addTo(map)
        map.flyTo({ center: [lon, lat] })
    })
}
