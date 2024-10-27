import { qsParse } from "./_qs"
import { isLatitude, isLongitude, isZoom } from "./_utils"
import { encodeMapState } from "./leaflet/_map-utils"

const body = document.querySelector("body.fixthemap-body")
if (body) {
    const params = qsParse(window.location.search.substring(1))
    let noteHref = "/note/new"

    // Support default location setting via URL parameters
    if (params.lon && params.lat) {
        const lon = Number.parseFloat(params.lon)
        const lat = Number.parseFloat(params.lat)
        // Zoom is optional and defaults to 17
        const zoom = params.zoom ? Number.parseInt(params.zoom, 10) : 17

        // Assign position only if it's valid
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            noteHref += encodeMapState({ lon, lat, zoom, layersCode: params.layers })
        }
    }

    const noteLink: HTMLAnchorElement = body.querySelector("a.note-link")
    noteLink.href = noteHref
}
