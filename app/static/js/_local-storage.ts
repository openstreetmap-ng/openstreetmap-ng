import { getUnixTimestamp, isLatitude, isLongitude, isZoom } from "./_utils"
import type { MapState } from "./leaflet/_map-utils"

const mapStateVersion = 1

/**
 * Get last map state from local storage
 * @example
 * getLastMapState()
 * // => { lon: 16.3725, lat: 48.208889, zoom: 12, layersCode: "K" }
 */
export const getLastMapState = (): MapState | null => {
    const lastMapState = localStorage.getItem("lastMapState")
    if (!lastMapState) return null
    const { version, lon, lat, zoom, layersCode } = JSON.parse(lastMapState)
    if (version === mapStateVersion && isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
        return { lon, lat, zoom, layersCode }
    }
    return null
}

/**
 * Set last map state to local storage
 * @example
 * setLastMapState({ lon: 16.3725, lat: 48.208889, zoom: 12, layersCode: "K" })
 */
export const setLastMapState = (state: MapState): void => {
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
 * @example
 * isBannerHidden("welcome")
 */
export const isBannerHidden = (name: string): boolean => localStorage.getItem(`bannerHidden-${name}`) !== null

/** Mark a banner as hidden in local storage */
export const markBannerHidden = (name: string): void => {
    console.debug("markBannerHidden", name)
    localStorage.setItem(`bannerHidden-${name}`, getUnixTimestamp().toString())
}

/**
 * Get last routing engine from local storage
 * @example
 * getLastRoutingEngine()
 * // => "graphhopper_car"
 */
export const getLastRoutingEngine = (): string | null => localStorage.getItem("lastRoutingEngine")

/**
 * Set last routing engine to local storage
 * @example
 * setLastRoutingEngine("graphhopper_car")
 */
export const setLastRoutingEngine = (engine: string): void => {
    console.debug("setLastRoutingEngine", engine)
    localStorage.setItem("lastRoutingEngine", engine)
}

/** Get access token for system app from local storage */
export const getSystemAppAccessToken = (clientId: string): string | null =>
    localStorage.getItem(`systemAppAccessToken-${clientId}`)

/** Set access token for system app to local storage */
export const setSystemAppAccessToken = (clientId: string, accessToken: string): void =>
    localStorage.setItem(`systemAppAccessToken-${clientId}`, accessToken)

/** Get last selected export format from local storage */
export const getLastSelectedExportFormat = (): string | null => localStorage.getItem("lastSelectedExportFormat")

/** Set last selected export format to local storage */
export const setLastSelectedExportFormat = (lastSelectedExportFormat: string): void => {
    console.debug("setLastSelectedExportFormat", lastSelectedExportFormat)
    localStorage.setItem("lastSelectedExportFormat", lastSelectedExportFormat)
}

/** Get tags diff mode state from local storage */
export const getTagsDiffMode = (): boolean => (localStorage.getItem("tagsDiffMode") ?? "true") === "true"

/** Set tags diff mode to local storage */
export const setTagsDiffMode = (state: boolean): void => {
    console.debug("setTagsDiffMode", state)
    localStorage.setItem("tagsDiffMode", state.toString())
}
