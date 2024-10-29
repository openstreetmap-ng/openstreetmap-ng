import "./_i18n"

import i18next from "i18next"
import * as L from "leaflet"
import { qsParse } from "./_qs"
import { isLatitude, isLongitude, zoomPrecision } from "./_utils"
import { type LayerId, getBaseLayerById, getDefaultBaseLayer } from "./leaflet/_layers"
import type { LonLatZoom } from "./leaflet/_map-utils"
import { getMarkerIcon } from "./leaflet/_utils"

const mapContainer = document.getElementById("map")
const map = L.map(mapContainer, {
    center: L.latLng(0, 0),
    zoom: 1,
})

// Parse search params
const searchParams = qsParse(location.search.substring(1))

// Set initial view
if (searchParams.bbox) {
    const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
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
    const coords = searchParams.marker.split(",").map(Number.parseFloat)
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
const layer = getBaseLayerById(searchParams.layer as LayerId) ?? getDefaultBaseLayer()
map.addLayer(layer)

/**
 * Get the fix the map link
 * @example
 * getFixTheMapLink(5.123456, 6.123456, 17)
 * // => "https://www.openstreetmap.org/fixthemap?lat=6.123456&lon=5.123456&zoom=17"
 */
const getFixTheMapLink = ({ lon, lat, zoom }: LonLatZoom): string => {
    const precision = zoomPrecision(zoom)
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    // TODO: test from within iframe
    return `${window.location.origin}/fixthemap?lat=${latFixed}&lon=${lonFixed}&zoom=${zoom}`
}

const reportProblemText = i18next.t("javascripts.embed.report_problem")

/** On move end, update the link with the current coordinates */
const onMoveEnd = () => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    const link = getFixTheMapLink({ lon: center.lng, lat: center.lat, zoom })
    map.attributionControl.setPrefix(`<a href="${link}" target="_blank">${reportProblemText}/a>`)
}

// Listen for events
map.addEventListener("moveend", onMoveEnd)

// Initial update to set the link
onMoveEnd()
