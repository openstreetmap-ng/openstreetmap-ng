import { qsParse, qsStringify } from "./_qs.js"
import { getMapParams, parseHash } from "./_utils.js"

const idIframe = document.querySelector(".id-iframe")
if (idIframe) {
    const dataset = idIframe.dataset
    const searchParams = qsParse(location.search.substring(1))
    const hashParams = qsParse(location.hash.substring(1))
    const mapParams = getMapParams(searchParams)
    const result = {}

    // Configure location
    if (mapParams.object) {
        // Location will be derived from the object
        result.id = mapParams.object.type[0] + mapParams.object.id

        // Optionally override location from hash
        const state = parseHash(location.hash)
        if (state.center) {
            result.map = `${state.zoom}/${state.center.lat}/${state.center.lng}`
        }
    } else if (dataset.lat && dataset.lon) {
        // TODO: is this still used?
        result.map = `16/${dataset.lat}/${dataset.lon}`
    } else {
        result.map = `${mapParams.zoom || 17}/${mapParams.lat}/${mapParams.lon}`
    }

    // Configure gpx
    if (dataset.gpx) {
        result.gpx = dataset.gpx
    } else if (hashParams.gpx) {
        result.gpx = hashParams.gpx
    }

    // Passthrough hash parameters
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
    idIframe.src = `${dataset.url}#${qsStringify(result)}`
}
