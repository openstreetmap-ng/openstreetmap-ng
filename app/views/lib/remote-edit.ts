import { API_URL } from "@lib/config"
import type { LonLatZoom } from "@lib/map/state"
import { qsEncode } from "@lib/qs"
import type { OSMObject } from "@lib/types"
import { t } from "i18next"

const REMOTE_EDIT_HOST = "http://localhost:8111"

/**
 * Get object request URL
 * @example
 * getObjectRequestUrl({ type: "node", id: 123456 })
 * // => "https://api.openstreetmap.org/api/0.6/node/123456"
 */
const getObjectRequestUrl = (object: OSMObject) => {
    const type = object.type === "note" ? "notes" : object.type

    // When requested for complex object, request for full version (incl. object's members)
    // Ignore version specification as there is a very high chance it will be rendered incorrectly
    if (type === "way" || type === "relation") {
        return `${API_URL}/api/0.6/${type}/${object.id}/full`
    }

    // @ts-expect-error
    const version = object.version
    return version
        ? `${API_URL}/api/0.6/${type}/${object.id}/${version}`
        : `${API_URL}/api/0.6/${type}/${object.id}`
}

const getBoundsFromCoords = ({ lon, lat, zoom }: LonLatZoom, paddingRatio = 0) => {
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

export const remoteEdit = async (button: HTMLButtonElement) => {
    console.debug("RemoteEdit: Opening", button)
    const remoteEditJson = button.dataset.remoteEdit
    if (!remoteEditJson) {
        console.error("RemoteEdit: Missing data-remote-edit")
        return
    }

    const { state, object }: { state: LonLatZoom; object?: OSMObject } =
        JSON.parse(remoteEditJson)
    const [minLon, minLat, maxLon, maxLat] = getBoundsFromCoords(state, 0.05)
    const loadQuery: Record<string, string> = {
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

    try {
        await fetch(`${REMOTE_EDIT_HOST}/load_and_zoom${qsEncode(loadQuery)}`, {
            method: "GET",
            mode: "no-cors",
            credentials: "omit",
            cache: "no-store",
            priority: "high",
        })

        // Optionally import note
        if (object && object.type === "note") {
            await fetch(
                `${REMOTE_EDIT_HOST}/import${qsEncode({ url: getObjectRequestUrl(object) })}`,
                {
                    method: "GET",
                    mode: "no-cors",
                    credentials: "omit",
                    cache: "no-store",
                    priority: "high",
                },
            )
        }
    } catch (error) {
        console.error("RemoteEdit: Failed", error)
        alert(t("site.index.remote_failed"))
    } finally {
        button.disabled = false
    }
}
