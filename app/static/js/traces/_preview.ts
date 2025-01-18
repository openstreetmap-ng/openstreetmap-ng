import { decode } from "@mapbox/polyline"
// @ts-ignore
import { antPath } from "leaflet-ant-path"
import { getGeolocateControl } from "../leaflet/_geolocate"
import { getDefaultBaseLayer } from "../leaflet/_layers"
import { addControlGroup, disableControlsClickPropagation } from "../leaflet/_map-utils"
import { getZoomControl } from "../leaflet/_zoom"

const antPathOptions = {
    delay: 1000,
    dashArray: [40, 60],
    weight: 4.5,
    color: "#f60",
    pulseColor: "#220",
    opacity: 1,
    keyboard: false,
    interactive: false,
}

const tracePreviewContainer = document.querySelector("div.trace-preview")
if (tracePreviewContainer) {
    console.debug("Initializing trace preview map")
    const isSmall = tracePreviewContainer.classList.contains("trace-preview-sm")

    const map = L.map(tracePreviewContainer, {
        attributionControl: !isSmall,
        zoomControl: false,
        minZoom: 3, // 2 would be better, but is buggy with leaflet animated pan
    })

    if (!isSmall) {
        // Add native controls
        map.addControl(L.control.scale())

        // Add custom zoom and location controls
        addControlGroup(map, [getZoomControl(), getGeolocateControl()])
    } else {
        // Add custom zoom controls
        addControlGroup(map, [getZoomControl()])
    }

    // Disable click propagation on controls
    disableControlsClickPropagation(map)

    // Add default layer
    map.addLayer(getDefaultBaseLayer())

    // Add trace path
    const coords = decode(tracePreviewContainer.dataset.line, 6)
    const path = antPath(coords, antPathOptions)
    map.addLayer(path)
    map.fitBounds(path.getBounds(), { animate: false })
}
