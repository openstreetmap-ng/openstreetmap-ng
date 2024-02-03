import i18next from "i18next"
import * as L from "leaflet"
import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"
import { getLastRoutingEngine, setLastRoutingEngine } from "../_local-storage.js"
import { qsParse } from "../_qs.js"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { zoomPrecision } from "../_utils.js"
import { getMarkerIcon } from "../leaflet/_utils.js"

export const routingStyles = {
    route: {
        color: "#0033ff",
        opacity: 0.3,
        weight: 10,
        interactive: false,
    },
    highlight: {
        color: "#ffff00",
        opacity: 0.5,
        weight: 12,
        interactive: false,
    },
}

/**
 * Create a new routing controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getRoutingController = (map) => {
    const sidebar = getActionSidebar("directions")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const fromInput = form.querySelector("input[name=from]")
    const toInput = form.querySelector("input[name=to]")
    const engineInput = form.querySelector("input[name=engine]") // TODO: load from local storage
    const bboxInput = form.querySelector("input[name=bbox]")
    const reverseButton = form.querySelector(".reverse-button")
    let loaded = false

    // Null values until initialized
    let fromMarker = null // green
    let toMarker = null // red
    let routePolyline = null
    let highlightPolyline = null
    let highlightPopup = null // TODO: autoPanPadding: [100, 100]

    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        }).addTo(map)

    /**
     * On marker drag end, update the form's coordinates
     * @param {L.DragEndEvent} event
     * @returns {void}
     */
    const onMarkerDragEnd = (event) => {
        const marker = event.propagatedFrom
        const latLng = marker.getLatLng()
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lon = latLng.lng.toFixed(precision)
        const lat = latLng.lat.toFixed(precision)
        const value = `${lat}, ${lon}`

        if (marker === fromMarker) {
            fromInput.value = value
            fromInput.dispatchEvent(new Event("input"))
        } else if (marker === toMarker) {
            toInput.value = value
            toInput.dispatchEvent(new Event("input"))
        } else {
            console.warn("Unknown routing marker", marker)
        }

        // TODO: resubmit form
    }

    /**
     * On map update, update the form's bounding box
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Skip updates if the sidebar is hidden
        if (!loaded) return

        bboxInput.value = map.getBounds().toBBoxString()
    }

    // On engine input change, remember the last routing engine
    const onEngineInputChange = () => {
        setLastRoutingEngine(engineInput.value)
    }

    // On reverse button click, swap the from and to inputs
    const onReverseButtonClick = () => {
        const fromValue = fromInput.value
        fromInput.value = toInput.value
        toInput.value = fromValue
        fromInput.dispatchEvent(new Event("input"))
        toInput.dispatchEvent(new Event("input"))

        // TODO: resubmit form
    }

    // On success callback, call routing engine, display results, and update search params
    const onFormSuccess = (data) => {
        // TODO:
    }

    // Listen for events
    configureStandardForm(form, onFormSuccess)
    map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    engineInput.addEventListener("input", onEngineInputChange)
    reverseButton.addEventListener("click", onReverseButtonClick)

    return {
        load: () => {
            form.reset()
            switchActionSidebar("directions")
            document.title = getPageTitle(sidebarTitle)

            let lastEngine = getLastRoutingEngine()

            // Allow default form setting via URL search parameters
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.engine) {
                lastEngine = searchParams.engine
            }

            if (searchParams.route) {
                // TODO:
            }

            if (lastEngine) {
                if (engineInput.querySelector(`option[value=${lastEngine}]`)) {
                    engineInput.value = lastEngine
                    engineInput.dispatchEvent(new Event("input"))
                } else {
                    console.warn(`Unknown routing engine: ${lastEngine}`)
                }
            }

            loaded = true

            // Initial update to set the inputs
            onMapZoomOrMoveEnd()
        },
        unload: () => {
            if (fromMarker) map.removeLayer(fromMarker)
            if (toMarker) map.removeLayer(toMarker)
            if (routePolyline) {
                map.removeLayer(routePolyline)
                routePolyline = null
            }
            if (highlightPolyline) {
                map.removeLayer(highlightPolyline)
                highlightPolyline = null
            }
            if (highlightPopup) map.closePopup(highlightPopup)

            loaded = false
        },
    }
}

/**
 * Format distance in meters
 * @param {number} meters Distance in meters
 * @returns {string} Formatted distance
 * @example
 * formatDistance(1100)
 * // => "1.1km"
 */
const formatDistance = (meters) => {
    // < 1 km
    if (meters < 1000) {
        return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters) })
    }
    // < 10 km
    if (meters < 10000) {
        return i18next.t("javascripts.directions.distance_km", { distance: (meters / 1000.0).toFixed(1) })
    }
    return i18next.t("javascripts.directions.distance_km", { distance: Math.round(meters / 1000) })
}

/**
 * Format height in meters
 * @param {number} meters Height in meters
 * @returns {string} Formatted height
 * @example
 * formatHeight(200)
 * // => "200m"
 */
const formatHeight = (meters) => {
    return i18next.t("javascripts.directions.distance_m", { distance: Math.round(meters) })
}

/**
 * Format time in seconds
 * @param {number} seconds Time in seconds
 * @returns {string} Formatted time
 * @example
 * formatTime(3600)
 * // => "1:00"
 */
const formatTime = (seconds) => {
    // TODO: nice hours and minutes text
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return `${h}:${m.toString().padStart(2, "0")}`
}
