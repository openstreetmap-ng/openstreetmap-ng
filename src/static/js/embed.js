import * as L from "leaflet"
import { qsParse } from "./_qs.js"
import { isLatitude, isLongitude, zoomPrecision } from "./_utils.js"
import { getBaseLayerById, getLayerIdByCode } from "./leaflet/_layers.js"
import { getMarkerIcon } from "./leaflet/_utils.js"

/**
 * Get the fix the map link
 * @param {number} lon The longitude
 * @param {number} lat The latitude
 * @param {number} zoom The zoom
 * @returns {string} The link
 * @example
 * getFixTheMapLink(5.123456, 6.123456, 17)
 * // => "https://www.openstreetmap.org/fixthemap?lat=6.123456&lon=5.123456&zoom=17"
 */
const getFixTheMapLink = (lon, lat, zoom) => {
    const precision = zoomPrecision(zoom)
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    return `https://www.openstreetmap.org/fixthemap?lat=${latFixed}&lon=${lonFixed}&zoom=${zoom}`
}

const reportProblemText = I18n.t("javascripts.embed.report_problem")

const searchParams = qsParse(location.search.substring(1))

// Backwards compatibility for old cyclemap id
if (searchParams.layer === "cycle map") searchParams.layer = "cyclemap"

const mapContainer = document.getElementById("map")
const map = L.map(mapContainer, {
    center: L.latLng(0, 0),
    zoom: 1,
})

// Set initial view
if (searchParams.bbox) {
    const bbox = searchParams.bbox.split(",").map(parseFloat)
    if (bbox.length === 4) {
        const [minLon, minLat, maxLon, maxLat] = bbox
        if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
            const bounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
            map.fitBounds(bounds, { animate: false })
        }
    }
}

// Add optional marker
if (searchParams.marker) {
    const coords = searchParams.marker.split(",").map(parseFloat)
    if (coords.length === 2) {
        const [lat, lon] = coords
        if (isLongitude(lon) && isLatitude(lat)) {
            const marker = L.marker(L.latLng(lat, lon), {
                icon: getMarkerIcon("blue", true),
                keyboard: false,
                interactive: false,
            })
            map.addLayer(marker)
        }
    }
}

// Use default layer when not specified or unknown
const layer = getBaseLayerById(searchParams.layer) ?? getBaseLayerById(getLayerIdByCode(""))
map.addLayer(layer)

// On move end, update the link
const onMoveEnd = () => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    const link = getFixTheMapLink(center.lng, center.lat, zoom)
    map.attributionControl.setPrefix(`<a href="${link}" target="_blank">${reportProblemText}/a>`)
}

// Listen for events
map.addEventListener("moveend", onMoveEnd)

// Initial update to set the link
onMoveEnd()
