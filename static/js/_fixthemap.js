import { qsParse } from "./_qs.js"
import { formatHash, isLatitude, isLongitude, isZoom } from "./_utils.js"

const noteIcon = document.querySelector(".fix-the-map-note-link")
if (noteIcon) {
    let href = "/note/new"

    // Support default location setting via URL parameters
    const params = qsParse(window.location.search.substring(1))
    if (params.lat && params.lon) {
        // Zoom is optional, default to 17
        params.zoom = parseInt(params.zoom || 17, 10)
        params.lat = parseFloat(params.lat)
        params.lon = parseFloat(params.lon)

        // Assign position only if it's valid
        if (isZoom(params.zoom) && isLatitude(params.lat) && isLongitude(params.lon)) href += formatHash(params)
    }

    noteIcon.setAttribute("href", href)
}
