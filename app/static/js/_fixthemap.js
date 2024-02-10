import { qsParse } from "./_qs.js"
import { isLatitude, isLongitude, isZoom } from "./_utils.js"
import { encodeMapState } from "./leaflet/_map-utils.js"

const noteIcon = document.querySelector(".fixthemap-note-link")
if (noteIcon) {
    const getStateFromSearch = () => {
        // Support default location setting via URL parameters
        const searchParams = qsParse(location.search.substring(1))
        if (searchParams.lon && searchParams.lat) {
            const lon = parseFloat(searchParams.lon)
            const lat = parseFloat(searchParams.lat)
            // Zoom is optional, defaults to 17
            const zoom = parseInt(searchParams.zoom ?? 17, 10)

            if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
                return { lon, lat, zoom, layersCode: "" }
            }
        }

        return null
    }

    const state = getStateFromSearch()
    const href = state ? `/note/new${encodeMapState(state)}` : "/note/new"
    noteIcon.setAttribute("href", href)
}
