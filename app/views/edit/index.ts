import { getInitialMapState, parseMapState } from "@lib/map/state"
import { qsEncode, qsParse } from "@lib/qs"
import { configureIFrameSystemApp } from "@lib/system-app"
import { NON_DIGIT_RE } from "@lib/utils"

import { filterValues } from "@std/collections/filter-values"
import { pick } from "@std/collections/pick"

const PASSTHROUGH_PARAMS = [
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
] as const

const initEmbeddedEditor = ({
    iframe,
    editorPath,
    clientId,
    logPrefix,
}: {
    iframe: HTMLIFrameElement
    editorPath: string
    clientId: "SystemApp.id" | "SystemApp.rapid"
    logPrefix: string
}) => {
    const searchParams = qsParse(window.location.search)
    const hashParams = qsParse(window.location.hash)
    let { lon, lat, zoom } = getInitialMapState()
    const params: Record<string, string | undefined> = {}

    // Optional scale instead of zoom (legacy, deprecated)
    if (searchParams.scale) {
        const scale = Number.parseFloat(searchParams.scale)
        if (scale > 0) zoom = Math.log(360 / (scale * 512)) / Math.log(2)
    }

    params.map = `${zoom}/${lat}/${lon}`

    // Optional object to select
    for (const type of ["node", "way", "relation", "note"] as const) {
        const idStr = searchParams[type]
        if (!idStr) continue

        const idDigits = idStr.replace(NON_DIGIT_RE, "")
        if (!idDigits || idDigits === "0") continue

        // Location will be derived from the object
        params.id = `${type[0]}${idDigits}`
        params.map = undefined

        // Optionally override location only from hash
        const hashState = parseMapState(window.location.hash)
        if (hashState) {
            params.map = `${hashState.zoom}/${hashState.lat}/${hashState.lon}`
        }
        break
    }

    // Optionally select gpx trace
    if (searchParams.gpx) {
        params.gpx = `${window.location.origin}/api/0.6/gpx/${searchParams.gpx}/data.gpx`
    } else if (hashParams.gpx) {
        params.gpx = `${window.location.origin}/api/0.6/gpx/${hashParams.gpx}/data.gpx`
    }

    // Passthrough some hash parameters
    Object.assign(params, filterValues(pick(hashParams, PASSTHROUGH_PARAMS), Boolean))

    const src = `${iframe.dataset.url}/${editorPath}${qsEncode(params, "#")}`
    const iframeOrigin = new URL(src).origin
    configureIFrameSystemApp(clientId, iframe, iframeOrigin)

    // Initialize iframe
    console.debug(`${logPrefix}: Initializing iframe`, src)
    iframe.src = src
}

const idIframe = document.querySelector("iframe.id-iframe")
if (idIframe)
    initEmbeddedEditor({
        iframe: idIframe,
        editorPath: "id",
        clientId: "SystemApp.id",
        logPrefix: "IDEditor",
    })

const rapidIframe = document.querySelector("iframe.rapid-iframe")
if (rapidIframe)
    initEmbeddedEditor({
        iframe: rapidIframe,
        editorPath: "rapid",
        clientId: "SystemApp.rapid",
        logPrefix: "RapidEditor",
    })
