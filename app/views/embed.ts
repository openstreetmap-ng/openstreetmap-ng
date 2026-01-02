import "./embed.scss"

import "@lib/i18n"
import { beautifyZoom, isLatitude, isLongitude, zoomPrecision } from "@lib/coords"
import { configureDefaultMapBehavior } from "@lib/map/defaults"
import {
    addMapLayer,
    addMapLayerSources,
    DEFAULT_LAYER_ID,
    type LayerId,
    resolveLayerCodeOrId,
} from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import type { LonLatZoom } from "@lib/map/state"
import { qsParse } from "@lib/qs"
import { t } from "i18next"
import {
    AttributionControl,
    Map as MaplibreMap,
    Marker,
    NavigationControl,
} from "maplibre-gl"

const mapContainer = document.getElementById("map")!
const attributionControl = new AttributionControl()
const map = new MaplibreMap({
    container: mapContainer,
    maxZoom: 19,
    zoom: 1,
    attributionControl: false,
    refreshExpiredTiles: false,
})
configureDefaultMapBehavior(map)

// Parse search params
const searchParams = qsParse(window.location.search)
const layerId = resolveLayerCodeOrId(searchParams.layer as LayerId) ?? DEFAULT_LAYER_ID
addMapLayerSources(map, layerId)

map.addControl(new NavigationControl({ showCompass: false }))
map.addControl(attributionControl)

// Set initial view
if (searchParams.bbox) {
    const bbox = searchParams.bbox.split(",").map(Number.parseFloat)
    if (bbox.length === 4) {
        const [minLon, minLat, maxLon, maxLat] = bbox
        if (
            isLongitude(minLon) &&
            isLatitude(minLat) &&
            isLongitude(maxLon) &&
            isLatitude(maxLat)
        ) {
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
                anchor: MARKER_ICON_ANCHOR,
                element: getMarkerIconElement("blue", true),
            })
                .setLngLat([lon, lat])
                .addTo(map)
        }
    }
}

addMapLayer(map, layerId)

const getFixTheMapLink = ({ lon, lat, zoom }: LonLatZoom) => {
    const zoomRounded = beautifyZoom(zoom)
    const precision = zoomPrecision(zoom)
    const lonFixed = lon.toFixed(precision)
    const latFixed = lat.toFixed(precision)
    // TODO: test from within iframe
    return `${window.location.origin}/fixthemap?lat=${latFixed}&lon=${lonFixed}&zoom=${zoomRounded}`
}

const reportProblemLink = document.createElement("a")
reportProblemLink.target = "_blank"
reportProblemLink.textContent = t("javascripts.embed.report_problem")

/** On move end, update the link with the current coordinates */
const onMoveEnd = () => {
    const center = map.getCenter()
    const zoom = map.getZoom()
    reportProblemLink.href = getFixTheMapLink({
        lon: center.lng,
        lat: center.lat,
        zoom,
    })
    attributionControl.options.customAttribution = reportProblemLink.outerHTML
    attributionControl._updateAttributions()
}

// Listen for events
map.on("moveend", onMoveEnd)

// Initial update to set the link
onMoveEnd()
