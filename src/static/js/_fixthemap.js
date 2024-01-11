import { encodeMapState } from "./_map_utils.js"
import { qsParse } from "./_qs.js"
import { isLatitude, isLongitude, isZoom } from "./_utils.js"

const noteIcon = document.querySelector(".fixthemap-note-link")
if (noteIcon) {
    // Support default location setting via URL parameters
    let locationProvided = false
    const searchParams = qsParse(location.search.substring(1))
    if (searchParams.lon && searchParams.lat) {
        searchParams.lon = parseFloat(searchParams.lon)
        searchParams.lat = parseFloat(searchParams.lat)
        // Zoom is optional, default to 17
        searchParams.zoom = parseInt(searchParams.zoom ?? 17, 10)

        if (isLongitude(searchParams.lon) && isLatitude(searchParams.lat) && isZoom(searchParams.zoom)) {
            locationProvided = true
        }
    }

    // Assign position only if it's valid
    let noteHref = "/note/new"
    if (locationProvided) noteHref += encodeMapState(searchParams)
    noteIcon.setAttribute("href", noteHref)
}
