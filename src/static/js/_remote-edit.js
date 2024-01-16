import * as L from "leaflet"
import { getObjectRequestUrl } from "./_api.js"
import { qsStringify } from "./_qs.js"
import "./_types.js"

const remoteEditHost = "http://127.0.0.1:8111"

let abortController = null

/**
 * Remotely edit an object
 * @param {L.Map} map Leaflet map
 * @param {OSMObject|null} object Optional OSM object
 * @returns {void}
 */
export const remoteEdit = (map, object = null) => {
    const bounds = map.getBounds()
    const padding = 0.0001 // I honestly don't know why this padding is needed
    const loadQuery = {
        left: bounds.getWest() - padding,
        top: bounds.getNorth() + padding,
        right: bounds.getEast() + padding,
        bottom: bounds.getSouth() - padding,
    }

    // Select object if specified
    if (object && object.type !== "note" && object.type !== "changeset") {
        loadQuery.select = `${object.type}${object.id}`
    }

    // Abort any pending requests
    if (abortController) abortController.abort()
    abortController = new AbortController()
    const abortSignal = abortController.signal

    fetch(`${remoteEditHost}/load_and_zoom?${qsStringify(loadQuery)}`, {
        mode: "no-cors",
        credentials: "omit",
        cache: "no-store",
        signal: abortSignal,
    })
        .then(() => {
            // Optionally import note
            if (object && object.type === "note") {
                return fetch(`${remoteEditHost}/import?${qsStringify({ url: getObjectRequestUrl(object) })}`, {
                    mode: "no-cors",
                    credentials: "omit",
                    cache: "no-store",
                    signal: abortSignal,
                })
            }
        })
        .catch((error) => {
            if (error.name === "AbortError") return
            console.error(error)
            alert(I18n.t("site.index.remote_failed"))
        })
        .finally(() => {
            abortController = null
        })
}
