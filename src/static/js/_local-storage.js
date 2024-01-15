import "./_types.js"
import { isLatitude, isLongitude, isZoom } from "./_utils.js"

const mapStateVersion = 1

/**
 * Get last map state from local storage
 * @returns {MapState|null} Map state object or null if invalid
 * @example
 * getLastMapState()
 * // => { lon: 16.3725, lat: 48.208889, zoom: 12, layersCode: "K" }
 */
export const getLastMapState = () => {
    const lastMapState = localStorage.getItem("lastMapState")
    if (!lastMapState) return null

    const { version, lon, lat, zoom, layersCode } = JSON.parse(lastMapState)

    // Check if values are valid
    if (version === mapStateVersion && isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
        return { lon, lat, zoom, layersCode }
    }

    return null
}

/**
 * Set last map state to local storage
 * @param {MapState} state Map state object
 * @returns {void}
 * @example
 * setLastMapState({ lon: 16.3725, lat: 48.208889, zoom: 12, layersCode: "K" })
 */
export const setLastMapState = (state) => {
    const { lon, lat, zoom, layersCode } = state
    localStorage.setItem(
        "lastMapState",
        JSON.stringify({
            version: mapStateVersion,
            lon,
            lat,
            zoom,
            layersCode,
        }),
    )
}

/**
 * Check whether user has hidden a banner
 * @param {string} name Banner name
 * @returns {boolean} Whether banner is hidden
 * @example
 * isBannerHidden("welcome")
 */
export const isBannerHidden = (name) => localStorage.getItem(`banner-hidden-${name}`) === "true"

/**
 * Mark a banner as hidden in local storage
 * @param {string} name Banner name
 * @returns {void}
 */
export const markBannerHidden = (name) => localStorage.setItem(`banner-hidden-${name}`, "true")
