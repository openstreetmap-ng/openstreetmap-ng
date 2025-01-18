import "./_i18n"
import i18next from "i18next"

import { AttributionControl, Map as MaplibreMap, Marker, NavigationControl } from "maplibre-gl"
import { qsParse } from "./_qs"
import { isLatitude, isLongitude, zoomPrecision } from "./_utils"
import { addMapLayer, addMapLayerSources, defaultLayerId, type LayerId, resolveLayerCodeOrId } from "./leaflet/_layers"
import type { LonLatZoom } from "./leaflet/_map-utils"
import { configureDefaultMapBehavior, getMarkerIconElement, markerIconAnchor } from "./leaflet/_utils"

const mapContainer = document.getElementById("map")
const attributionControl = new AttributionControl()
const map = new MaplibreMap({
    container: mapContainer,
    maxZoom: 19,
    zoom: 1,
    attributionControl: false,
    refreshExpiredTiles: false,
})
configureDefaultMapBehavior(map)
addMapLayerSources(map, "base")
map.addControl(new NavigationControl({ showCompass: false }))
map.addControl(attributionControl)

// Parse search params
const searchParams = qsParse(location.search.substring(1))

// Set initial view
if (searchParams.bbox) {
    const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
    if (bbox.length === 4) {
        const [minLon, minLat, maxLon, maxLat] = bbox
        if (isLongitude(minLon) && isLatitude(minLat) && isLongitude(maxLon) && isLatitude(maxLat)) {
            map.fitBounds([minLon, minLat, maxLon, maxLat], { animate: false })
        }
    }
}

// Add optional marker
if (searchParams.marker) {
    const coords = searchParams.marker.split(",").map(Number.parseFloat)
    if (coords.length === 2) {
        const [lat, lon] = coords
        if (isLongitude(lon) && isLatitude(lat)) {
            new Marker({
                anchor: markerIconAnchor,
                element: getMarkerIconElement("blue", true),
            })
                .setLngLat([lon, lat])
                .addTo(map)
        }
    }
}

const layerId = resolveLayerCodeOrId(searchParams.layer as LayerId) ?? defaultLayerId
addMapLayer(map, layerId)

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

const reportProblemLink = document.createElement("a")
reportProblemLink.target = "_blank"
reportProblemLink.textContent = i18next.t("javascripts.embed.report_problem")

/** On move end, update the link with the current coordinates */
const onMoveEnd = () => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    reportProblemLink.href = getFixTheMapLink({ lon: center.lng, lat: center.lat, zoom })
    attributionControl.options.customAttribution = reportProblemLink.outerHTML
    attributionControl._updateAttributions()
}

// Listen for events
map.on("moveend", onMoveEnd)

// Initial update to set the link
onMoveEnd()
