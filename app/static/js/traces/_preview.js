import * as L from "leaflet"
import { antPath } from "leaflet-ant-path"
import { getGeolocateControl } from "../leaflet/_geolocate-control"
import { getDefaultBaseLayer } from "../leaflet/_layers.js"
import { addControlGroup } from "../leaflet/_map-utils"
import { getZoomControl } from "../leaflet/_zoom-control"

const antPathOptions = {
    delay: 1000,
    dashArray: [30, 70],
    weight: 3.5,
    color: "#F60",
    pulseColor: "#220",
    opacity: 0.8,
    keyboard: false,
    interactive: false,
}

const tracePreviewContainer = document.querySelector(".trace-preview")
if (tracePreviewContainer) {
    console.debug("Initializing trace preview map")
    const isSmall = tracePreviewContainer.classList.contains("trace-preview-sm")
    const coords = JSON.parse(tracePreviewContainer.dataset.coords)
    const coords2D = []
    for (let i = 0; i < coords.length; i += 2) {
        coords2D.push([coords[i + 1], coords[i]])
    }

    const map = L.map(tracePreviewContainer, {
        attributionControl: !isSmall,
        zoomControl: false,
        maxBoundsViscosity: 1,
        minZoom: 3, // 2 would be better, but is buggy with leaflet animated pan
        maxBounds: L.latLngBounds(L.latLng(-85, Number.NEGATIVE_INFINITY), L.latLng(85, Number.POSITIVE_INFINITY)),
    })

    if (!isSmall) {
        // Disable Leaflet's attribution prefix
        map.attributionControl.setPrefix(false)

        // Add native controls
        map.addControl(L.control.scale())

        // Add custom zoom and location controls
        addControlGroup(map, [getZoomControl(), getGeolocateControl()])
    } else {
        // Add custom zoom controls
        addControlGroup(map, [getZoomControl()])
    }

    // Add default layer
    map.addLayer(getDefaultBaseLayer())

    // Add trace path
    const path = antPath(coords2D, antPathOptions)
    map.addLayer(path)
    map.fitBounds(path.getBounds(), { animate: false })
}
