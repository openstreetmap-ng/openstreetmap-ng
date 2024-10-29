import { qsParse } from "./_qs"
import { isLatitude, isLongitude, isZoom } from "./_utils"
import { encodeMapState } from "./leaflet/_map-utils"

const body = document.querySelector("body.fixthemap-body")
if (body) {
    const params = qsParse(window.location.search.substring(1))
    let noteHref = "/note/new"

    // Supports default location setting via URL parameters
    if (params.lon && params.lat) {
        const lon = Number.parseFloat(params.lon)
        const lat = Number.parseFloat(params.lat)
        const zoom = params.zoom ? Number.parseInt(params.zoom, 10) : 17
        if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
            noteHref += encodeMapState({ lon, lat, zoom, layersCode: params.layers })
        }
    }

    const noteLink = body.querySelector("a.note-link")
    noteLink.href = noteHref
}
