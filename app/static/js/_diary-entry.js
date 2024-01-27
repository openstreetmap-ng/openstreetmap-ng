import i18next from "i18next"
import * as L from "leaflet"
import { isLatitude, isLongitude, zoomPrecision } from "./_utils.js"
import { getBaseLayerById, getLayerIdByCode } from "./leaflet/_layers.js"
import { getMarkerIcon } from "./leaflet/_utils.js"
import { getZoomControl } from "./leaflet/_zoom-control.js"

const useMapContainer = document.querySelector(".diary-entry-use-map-container")
if (useMapContainer) {
    const lonInput = useMapContainer.querySelector("input[name=longitude]")
    const latInput = useMapContainer.querySelector("input[name=latitude]")
    const useMapButton = useMapContainer.querySelector(".use-map-btn")
    const mapDiv = useMapContainer.querySelector(".leaflet-container")

    // Null values until the map/marker is initialized
    let map = null
    let marker = null

    const markerFactory = (latLng) =>
        L.marker(latLng, { icon: getMarkerIcon("red", true) })
            .bindPopup(i18next.t("diary_entries.edit.marker_text"))
            .addTo(map)

    // On map click, update the coordinates and move the marker
    const onMapClick = (e) => {
        const precision = zoomPrecision(map.getZoom())
        const lon = e.latlng.lng.toFixed(precision)
        const lat = e.latlng.lat.toFixed(precision)
        const latLng = L.latLng(lat, lon)

        lonInput.value = lon
        latInput.value = lat

        // If there's already a marker, move it, otherwise create a new one
        if (marker) marker.setLatLng(latLng)
        else marker = markerFactory(latLng)
    }

    // On "Use Map" button click, show the map and hide the button
    const onUseMapButtonClick = () => {
        useMapButton.classList.add("d-none")
        mapDiv.classList.remove("d-none")
        const params = mapDiv.dataset

        map = L.map(mapDiv, {
            attributionControl: false,
            zoomControl: false,
        })

        // Add default layer
        map.addLayer(getBaseLayerById(getLayerIdByCode("")))

        // Add custom zoom control
        map.addControl(getZoomControl())

        let center

        // Attempt to parse the lat/lon from the inputs
        // If they're valid, use them as the initial center and display a marker
        if (lonInput.value && latInput.value) {
            const lon = parseFloat(lonInput.value)
            const lat = parseFloat(latInput.value)
            if (isLongitude(lon) && isLatitude(lat)) {
                center = L.latLng(lat, lon)
                marker = markerFactory(center)
                // TODO: draggable marker
            }
        }

        // When input is not valid, use the default center
        // This will only focus the map, not display a marker
        if (center === undefined) {
            center = L.latLng(params.lat, params.lon)
        }

        map.setView(center, params.zoom)
        map.addEventListener("click", onMapClick)
    }

    // Listen for events
    useMapButton.addEventListener("click", onUseMapButtonClick)
}
