import { getInitialMapState, parseMapState } from "@lib/map/state"
import { qsEncode, qsParse } from "@lib/qs"
import { configureIFrameSystemApp } from "@lib/system-app"

const iframe = document.querySelector("iframe.rapid-iframe")
if (iframe) {
    const hashParams = qsParse(window.location.hash)
    const searchParams = qsParse(window.location.search)
    const { lon, lat, zoom } = getInitialMapState()
    const params: Record<string, string> = {}

    params.map = `${zoom}/${lat}/${lon}`

    // Optional object to select
    for (const type of ["node", "way", "relation", "note"]) {
        if (searchParams[type]) {
            const id = Number.parseInt(searchParams[type], 10)
            if (!Number.isInteger(id) || id <= 0) continue

            // Location will be derived from the object
            params.id = `${type[0]}${id}`
            params.map = undefined

            // Optionally override location only from hash
            const hashState = parseMapState(window.location.hash)
            if (hashState) {
                params.map = `${hashState.zoom}/${hashState.lat}/${hashState.lon}`
            }

            break
        }
    }

    // Optionally select gpx trace
    if (searchParams.gpx) {
        params.gpx = `${window.location.origin}/api/0.6/gpx/${searchParams.gpx}/data.gpx`
    } else if (hashParams.gpx) {
        params.gpx = `${window.location.origin}/api/0.6/gpx/${hashParams.gpx}/data.gpx`
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
        if (value) params[param] = value
    }

    const src = `${iframe.dataset.url}/rapid${qsEncode(params, "#")}`
    const iframeOrigin = new URL(src).origin
    configureIFrameSystemApp("SystemApp.rapid", iframe, iframeOrigin)

    // Initialize iframe
    console.debug("Initializing Rapid iframe", src)
    iframe.src = src
}
