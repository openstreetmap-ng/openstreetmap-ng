import i18next from "i18next"
import { apiUrl } from "./_config"
import { qsEncode } from "./_qs"
import type { Bounds, OSMObject } from "./_types"
import type { LonLatZoom } from "./leaflet/_map-utils"

const remoteEditHost = "http://127.0.0.1:8111"

/**
 * Get object request URL
 * @example
 * getObjectRequestUrl({ type: "node", id: 123456 })
 * // => "https://api.openstreetmap.org/api/0.6/node/123456"
 */
const getObjectRequestUrl = (object: OSMObject): string => {
    const type = object.type === "note" ? "notes" : object.type

    // When requested for complex object, request for full version (incl. object's members)
    // Ignore version specification as there is a very high chance it will be rendered incorrectly
    if (type === "way" || type === "relation") {
        return `${apiUrl}/api/0.6/${type}/${object.id}/full`
    }

    // @ts-ignore
    const version: number | null = object.version
    return version ? `${apiUrl}/api/0.6/${type}/${object.id}/${version}` : `${apiUrl}/api/0.6/${type}/${object.id}`
}

/** Get bounds from coordinates and zoom level */
const getBoundsFromCoords = ({ lon, lat, zoom }: LonLatZoom, paddingRatio = 0): Bounds => {
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

/** Start remote edit in JOSM */
export const remoteEdit = (button: HTMLButtonElement): void => {
    console.debug("remoteEdit", button)
    const remoteEditJson = button.dataset.remoteEdit
    if (!remoteEditJson) {
        console.error("Remote edit button is missing data-remote-edit")
        return
    }

    const { state, object }: { state: LonLatZoom; object?: OSMObject } = JSON.parse(remoteEditJson)
    const [minLon, minLat, maxLon, maxLat] = getBoundsFromCoords(state, 0.05)
    const loadQuery: { [key: string]: string } = {
        left: minLon.toString(),
        bottom: minLat.toString(),
        right: maxLon.toString(),
        top: maxLat.toString(),
    }

    // Select object if specified
    if (object && object.type !== "note" && object.type !== "changeset") {
        loadQuery.select = `${object.type}${object.id}`
    }

    // Disable button while loading
    button.disabled = true

    const loadAndZoomQuery = qsEncode(loadQuery)
    fetch(`${remoteEditHost}/load_and_zoom?${loadAndZoomQuery}`, {
        method: "GET",
        mode: "no-cors",
        credentials: "omit",
        cache: "no-store",
        priority: "high",
    })
        .then(() => {
            // Optionally import note
            if (object && object.type === "note") {
                const importQuery = qsEncode({ url: getObjectRequestUrl(object) })
                return fetch(`${remoteEditHost}/import?${importQuery}`, {
                    method: "GET",
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
