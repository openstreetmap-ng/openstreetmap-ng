import { qsParse } from "./_qs.js"
import { isLatitude, isLongitude, isZoom } from "./_utils.js"
import { encodeMapState } from "./leaflet/_map-utils.js"

const fixthemapBody = document.querySelector("body.fixthemap-body")
if (fixthemapBody) {
    const noteLink = fixthemapBody.querySelector(".note-link")

    // Support default location setting via URL parameters
    let locationProvided = false
    const params = qsParse(location.search.substring(1))
    if (params.lon && params.lat) {
        params.lon = parseFloat(params.lon)
        params.lat = parseFloat(params.lat)
        // Zoom is optional, defaults to 17
        params.zoom = parseInt(params.zoom ?? 17, 10)

        if (isLongitude(params.lon) && isLatitude(params.lat) && isZoom(params.zoom)) {
            locationProvided = true
        }
    }

    // Assign position only if it's valid
    let noteHref = "/note/new"
    if (locationProvided) noteHref += encodeMapState(params)
    noteLink.setAttribute("href", noteHref)
}
