import * as L from "leaflet"
import { getLastMapState } from "./_local-storage.js"
import { parseMapState } from "./_map-utils.js"
import { homePoint } from "./_params.js"
import { qsParse, qsStringify } from "./_qs.js"
import { isLatitude, isLongitude, isZoom } from "./_utils.js"

/**
 * Convert search parameters to iD parameters
 * @param {object} searchParams Search parameters
 */
const convertSearchParams = (searchParams) => {
    const result = {}
    // Slightly better type hinting
    result.lon = undefined
    result.lat = undefined
    result.zoom = undefined
    result.bounds = undefined

    // Marker parameters
    if (searchParams.mlat && searchParams.mlon) {
        const mlon = parseFloat(searchParams.mlon)
        const mlat = parseFloat(searchParams.mlat)
        if (isLongitude(mlon) && isLatitude(mlat)) {
            result.marker = true
            result.mlon = mlon
            result.mlat = mlat
        }
    }

    // Old style object parameters
    for (const type of ["node", "way", "relation", "note"]) {
        if (searchParams[type]) {
            const id = parseInt(searchParams[type], 10)
            if (id > 0) {
                result.object = { type: type, id: id }
                break
            }
        }
    }

    const state = parseMapState(location.hash)
    const lastLocation = getLastMapState()

    // Decide on the initial position and zoom
    const setPosition = (result) => {
        // 1. Use the position from the hash state
        if (state) {
            result.lon = state.lon
            result.lat = state.lat
            result.zoom = state.zoom
            return
        }

        // 2. Use the bounds from the bbox query parameter
        if (searchParams.bbox) {
            const bbox = searchParams.bbox.split(",").map(parseFloat)
            if (bbox.length === 4) {
                const [minLon, minLat, maxLon, maxLat] = bbox
                if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
                    result.bounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
                    return
                }
            }
        }

        // 3. Use the bounds from minlon, minlat, maxlon, maxlat query parameters
        if (searchParams.minlon && searchParams.minlat && searchParams.maxlon && searchParams.maxlat) {
            const minLon = parseFloat(searchParams.minlon)
            const minLat = parseFloat(searchParams.minlat)
            const maxLon = parseFloat(searchParams.maxlon)
            const maxLat = parseFloat(searchParams.maxlat)
            if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
                result.bounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
                return
            }
        }

        // 4. Use the position from the marker
        if (result.marker) {
            const zoom = parseInt(searchParams.zoom ?? 12, 10)
            if (isZoom(zoom)) {
                result.lon = result.mlon
                result.lat = result.mlat
                result.zoom = zoom
                return
            }
        }

        // 5. Use the last location from local storage
        if (lastLocation) {
            result.lon = lastLocation.lon
            result.lat = lastLocation.lat
            result.zoom = lastLocation.zoom
            return
        }

        // 6. Use the user home location
        if (homePoint) {
            const [lon, lat] = JSON.parse(homePoint)
            result.lon = lon
            result.lat = lat
            result.zoom = 10
            return
        }

        // 7. Use the default location
        result.lon = 0
        result.lat = 30
        result.zoom = 3
    }

    setPosition(result)

    // Decide on the initial layer
    result.layer = state?.layersCode ?? lastLocation?.layersCode ?? ""

    // Apply optional scaling
    const scale = parseFloat(searchParams.scale)
    if (scale > 0) result.zoom = Math.log(360 / (scale * 512)) / Math.log(2)

    return result
}

const idIframe = document.querySelector(".id-iframe")
if (idIframe) {
    console.debug("Initializing iD iframe")

    const dataset = idIframe.dataset
    const searchParams = qsParse(location.search.substring(1))
    const hashParams = qsParse(location.hash.substring(1))
    const params = convertSearchParams(searchParams)
    const result = {}

    // Configure location
    if (params.object) {
        // Location will be derived from the object
        result.id = params.object.type[0] + params.object.id

        // Optionally override location from hash
        const state = parseMapState(location.hash)
        if (state) result.map = `${state.zoom}/${state.lat}/${state.lon}`
    } else if (dataset.lat && dataset.lon) {
        // TODO: is this still used?
        result.map = `16/${dataset.lat}/${dataset.lon}`
    } else {
        result.map = `${params.zoom ?? 17}/${params.lat}/${params.lon}`
    }

    // Configure gpx
    if (dataset.gpx) {
        result.gpx = dataset.gpx
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
    idIframe.src = `${dataset.url}#${qsStringify(result)}`
}
