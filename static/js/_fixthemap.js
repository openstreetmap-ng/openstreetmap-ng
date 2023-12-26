import { qsParse } from "./_qs.js"
import { formatHash, isLatitude, isLongitude, isZoom } from "./_utils.js"

const noteIcon = document.querySelector(".fixthemap-note-link")
if (noteIcon) {
    // Support default location setting via URL parameters
    let locationProvided = false
    const params = qsParse(window.location.search.substring(1))
    if (params.lat && params.lon) {
        // Zoom is optional, default to 17
        params.zoom = parseInt(params.zoom || 17, 10)
        params.lat = parseFloat(params.lat)
        params.lon = parseFloat(params.lon)

        if (isZoom(params.zoom) && isLatitude(params.lat) && isLongitude(params.lon)) locationProvided = true
    }

    // Assign position only if it's valid
    let noteHref = "/note/new"
    if (locationProvided) noteHref += formatHash(params)
    noteIcon.setAttribute("href", noteHref)
}
