import "./_types.js"
import { getUnixTimestamp, isLatitude, isLongitude, isZoom } from "./_utils.js"

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
export const isBannerHidden = (name) => localStorage.getItem(`bannerHidden-${name}`) !== null

/**
 * Mark a banner as hidden in local storage
 * @param {string} name Banner name
 * @returns {void}
 */
export const markBannerHidden = (name) => {
    console.debug("markBannerHidden", name)
    localStorage.setItem(`bannerHidden-${name}`, getUnixTimestamp())
}

/**
 * Get last routing engine from local storage
 * @returns {string|null} Last routing engine identifier
 * @example
 * getLastRoutingEngine()
 * // => "graphhopper_car"
 */
export const getLastRoutingEngine = () => localStorage.getItem("lastRoutingEngine")

/**
 * Set last routing engine to local storage
 * @param {string} engine Routing engine identifier
 * @returns {void}
 * @example
 * setLastRoutingEngine("graphhopper_car")
 */
export const setLastRoutingEngine = (engine) => {
    console.debug("setLastRoutingEngine", engine)
    localStorage.setItem("lastRoutingEngine", engine)
}

/**
 * Get access token for system app from local storage
 * @param {string} clientId System app client ID
 * @returns {string|null} Access token
 */
export const getSystemAppAccessToken = (clientId) => localStorage.getItem(`systemAppAccessToken-${clientId}`)

/**
 * Set access token for system app to local storage
 * @param {string} clientId System app client ID
 * @param {string} accessToken Access token
 * @returns {void}
 */
export const setSystemAppAccessToken = (clientId, accessToken) =>
    localStorage.setItem(`systemAppAccessToken-${clientId}`, accessToken)

const lastSelectedExportFormatKey = "lastSelectedExportFormat"

/**
 * Get last selected export format from local storage
 * @returns {string|null} Last selected export format
 */
export const getLastSelectedExportFormat = () => localStorage.getItem(lastSelectedExportFormatKey)

/**
 * Set last selected export format to local storage
 * @param {string} lastSelectedExportFormat Last selected export format
 * @returns {void}
 */
export const setLastSelectedExportFormat = (lastSelectedExportFormat) => {
    console.debug("setLastSelectedExportFormat", lastSelectedExportFormat)
    localStorage.setItem(lastSelectedExportFormatKey, lastSelectedExportFormat)
}

/**
 * Get tags diff mode from local storage
 * @returns {boolean} Tags diff mode
 */
export const getTagsDiffMode = () => (localStorage.getItem("tagsDiffMode") ?? "true") === "true"

/**
 * Set tags diff mode to local storage
 * @param {boolean} state Tags diff mode
 * @returns {void}
 */
export const setTagsDiffMode = (state) => {
    console.debug("setTagsDiffMode", state)
    localStorage.setItem("tagsDiffMode", state)
}
