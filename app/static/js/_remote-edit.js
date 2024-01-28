import i18next from "i18next"
import { apiUrl } from "./_config.js"
import { qsEncode } from "./_qs.js"
import "./_types.js"

const remoteEditHost = "http://127.0.0.1:8111"

/**
 * Get object request URL
 * @param {OSMObject} object OSM object
 * @returns {string} Request URL
 * @example
 * getObjectRequestUrl({ type: "node", id: 123456 })
 * // => "https://api.openstreetmap.org/api/0.6/node/123456"
 */
const getObjectRequestUrl = (object) => {
    const type = object.type === "note" ? "notes" : object.type

    // When requested for complex object, request for full version (incl. object's members)
    // Ignore version specification as there is a very high chance it will be rendered incorrectly
    if (type === "way" || type === "relation") {
        return `${apiUrl}/api/0.6/${type}/${object.id}/full`
    }

    if (object.version) {
        return `${apiUrl}/api/0.6/${type}/${object.id}/${object.version}`
    }

    return `${apiUrl}/api/0.6/${type}/${object.id}`
}

/**
 * Get bounds from coordinates and zoom level
 * @param {number} lon Longitude
 * @param {number} lat Latitude
 * @param {number} zoom Zoom level
 * @param {number} paddingRatio Optional padding ratio to extend the bounds by
 * @returns {number[]} Bounds array in the [minLon, minLat, maxLon, maxLat] format
 */
const getBoundsFromCoords = (lon, lat, zoom, paddingRatio = 0) => {
    // Assume the map takes up the entire screen
    const mapHeight = window.innerHeight
    const mapWidth = window.innerWidth

    const tileSize = 256
    const tileCountHalfX = mapWidth / tileSize / 2
    const tileCountHalfY = mapHeight / tileSize / 2

    const n = 2 ** zoom
    const deltaLon = (tileCountHalfX / n) * 360 * (1 + paddingRatio)
    const deltaLat = (tileCountHalfY / n) * 180 * (1 + paddingRatio)

    return [lon - deltaLon, lat - deltaLat, lon + deltaLon, lat + deltaLat]
}

/**
 * Remotely edit an object
 * @param {HTMLButtonElement} button The button element
 * @param {number[]} bounds Bounds array in the [minLon, minLat, maxLon, maxLat] format
 * @param {OSMObject|null} object Optional OSM object
 * @returns {void}
 */
const remoteEdit = (button, bounds, object = null) => {
    const [minLon, minLat, maxLon, maxLat] = bounds
    const loadQuery = {
        left: minLon,
        bottom: minLat,
        right: maxLon,
        top: maxLat,
    }

    // Select object if specified
    if (object && object.type !== "note" && object.type !== "changeset") {
        loadQuery.select = `${object.type}${object.id}`
    }

    // Disable button while loading
    button.disabled = true

    fetch(`${remoteEditHost}/load_and_zoom`, {
        method: "GET",
        body: qsEncode(loadQuery),
        mode: "no-cors",
        credentials: "omit",
        cache: "no-store",
        priority: "high",
    })
        .then(() => {
            // Optionally import note
            if (object && object.type === "note") {
                return fetch(`${remoteEditHost}/import`, {
                    method: "GET",
                    body: qsEncode({ url: getObjectRequestUrl(object) }),
                    mode: "no-cors",
                    credentials: "omit",
                    cache: "no-store",
                    priority: "high",
                })
            }
        })
        .catch((error) => {
            console.error("Failed to edit remotely", error)
            alert(i18next.t("site.index.remote_failed"))
        })
        .finally(() => {
            button.disabled = false
        })
}

/**
 * Configure the remote edit button
 * @param {HTMLButtonElement} button The button element
 * @returns {void}
 */
export const configureRemoteEditButton = (button) => {
    const onButtonClick = () => {
        const data = button.dataset.remoteEdit
        if (!data) {
            console.error("Missing remote edit data")
            return
        }

        const { state, object } = JSON.parse(data)
        const bounds = getBoundsFromCoords(state.lon, state.lat, state.zoom, 0.05)
        remoteEdit(button, bounds, object)
    }

    // Listen for events
    button.addEventListener("click", onButtonClick)
}
