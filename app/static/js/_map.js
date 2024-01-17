import { configureFindHomeButton } from "./leaflet/_find-home.js"
import { getMainMap } from "./leaflet/_map.js"

const mapContainer = document.querySelector(".map-container")
if (mapContainer) {
    const map = getMainMap(mapContainer.querySelector(".main-map"))

    // Configure here instead of navbar to avoid global script dependency (navbar is global)
    const findHomeButton = document.querySelector(".find-home")
    if (findHomeButton) configureFindHomeButton(map, findHomeButton)
}
