import { getMainMap } from "./leaflet/_map.js"

const mapContainer = document.querySelector(".main-map")
if (mapContainer) {
    const map = getMainMap(mapContainer)
}
