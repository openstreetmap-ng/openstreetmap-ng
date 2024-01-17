import { getInitialMapState, parseMapState } from "./_map-utils.js"
import { idUrl } from "./_params.js"
import { qsParse, qsStringify } from "./_qs.js"

const idIframe = document.querySelector(".id-iframe")
if (idIframe) {
    const hashParams = qsParse(location.hash.substring(1))
    const searchParams = qsParse(location.search.substring(1))
    let { lon, lat, zoom } = getInitialMapState()
    const result = {}

    // Optional scale instead of zoom
    if (searchParams.scale) {
        const scale = parseFloat(searchParams.scale)
        if (scale > 0) zoom = Math.log(360 / (scale * 512)) / Math.log(2)
    }

    result.map = `${zoom}/${lat}/${lon}`

    // Optional object to select
    for (const type of ["node", "way", "relation", "note"]) {
        if (searchParams[type]) {
            const id = parseInt(searchParams[type], 10)
            if (!Number.isInteger(id) || id <= 0) continue

            // Location will be derived from the object
            result.id = `${type[0]}${id}`
            result.map = undefined

            // Optionally override location only from hash
            const hashState = parseMapState(location.hash)
            if (hashState) {
                result.map = `${hashState.zoom}/${hashState.lat}/${hashState.lon}`
            }

            break
        }
    }

    // Optionally select gpx trace
    if (searchParams.gpx) {
        result.gpx = searchParams.gpx
    } else if (hashParams.gpx) {
        result.gpx = hashParams.gpx
    }

    // Passthrough some hash parameters
    for (const param of [
        "background",
        "comment",
        "disable_features",
        "hashtags",
        "locale",
        "maprules",
        "offset",
        "photo",
        "photo_dates",
        "photo_overlay",
        "photo_username",
        "presets",
        "source",
        "validationDisable",
        "validationWarning",
        "validationError",
        "walkthrough",
    ]) {
        const value = hashParams[param]
        if (value) result[param] = value
    }

    // Initialize iframe
    idIframe.src = `${idUrl}#${qsStringify(result)}`
}
