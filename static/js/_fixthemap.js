import { qsParse } from "./_qs.js"
import { formatHash, isLatitude, isLongitude } from "./_utils.js"

const noteIcon = document.querySelector(".fix-the-map-note-link")
if (noteIcon) {
    let href = "/note/new"

    // Support default location setting via URL parameters
    const params = qsParse(window.location.search.substring(1))
    if (params.lat && params.lon) {
        params.lat = parseFloat(params.lat)
        params.lon = parseFloat(params.lon)
        if (params.zoom) params.zoom = parseInt(params.zoom)
        params.zoom = params.zoom || 17
        if (isLatitude(params.lat) && isLongitude(params.lon)) {
            href += formatHash(params)
        }
    }

    noteIcon.setAttribute("href", href)
}
