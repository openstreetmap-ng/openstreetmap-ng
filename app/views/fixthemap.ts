import { qsParse } from "./lib/qs"
import { isLatitude, isLongitude, isZoom } from "./lib/utils"
import { encodeMapState } from "./lib/map/map-utils"

const body = document.querySelector("body.fixthemap-body")
if (body) {
    const params = qsParse(window.location.search)
    let noteHref = "/note/new"

    // Supports default location setting via URL parameters
    if (params.lon && params.lat) {
        const lon = Number.parseFloat(params.lon)
        const lat = Number.parseFloat(params.lat)
        const zoom = params.zoom ? Number.parseFloat(params.zoom) : 17
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            noteHref += encodeMapState({ lon, lat, zoom, layersCode: params.layers })
        }
    }

    const noteLink = body.querySelector("a.note-link")
    noteLink.href = noteHref
}
