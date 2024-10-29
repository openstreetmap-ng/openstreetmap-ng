import i18next from "i18next"
import * as L from "leaflet"
import { isLatitude, isLongitude, zoomPrecision } from "./_utils"
import { getDefaultBaseLayer } from "./leaflet/_layers"
import { getMarkerIcon } from "./leaflet/_utils"
import { getZoomControl } from "./leaflet/_zoom-control"

// TODO: diary entry new body
const useMapContainer = document.querySelector(".diary-entry-use-map-container")
if (useMapContainer) {
    const lonInput = useMapContainer.querySelector("input[name=longitude]")
    const latInput = useMapContainer.querySelector("input[name=latitude]")
    const mapDiv = useMapContainer.querySelector("div.leaflet-container")

    let map: L.Map | null = null
    let marker: L.Marker | null = null

    const markerFactory = (latLng: L.LatLngExpression) =>
        L.marker(latLng, { icon: getMarkerIcon("red", true) })
            .bindPopup(i18next.t("diary_entries.edit.marker_text"))
            .addTo(map)

    /** On map click, update the coordinates and move the marker */
    const onMapClick = (e: L.LeafletMouseEvent) => {
        const precision = zoomPrecision(map.getZoom())
        const lon = e.latlng.lng.toFixed(precision)
        const lat = e.latlng.lat.toFixed(precision)
        const latLng = L.latLng(Number(lat), Number(lon))

        lonInput.value = lon
        latInput.value = lat

        // If there's already a marker, move it, otherwise create a new one
        if (marker) marker.setLatLng(latLng)
        else marker = markerFactory(latLng)
    }

    const useMapButton = useMapContainer.querySelector("button.use-map-btn")
    useMapButton.addEventListener("click", () => {
        // On "Use Map" button click, show the map and hide the button
        useMapButton.classList.add("d-none")
        mapDiv.classList.remove("d-none")
        const params = mapDiv.dataset

        map = L.map(mapDiv, {
            attributionControl: false,
            zoomControl: false,
        })

        // Add default layer
        map.addLayer(getDefaultBaseLayer())

        // Add custom zoom control
        map.addControl(getZoomControl())

        let center: L.LatLng | null = null

        // Attempt to parse the lat/lon from the inputs
        // If they're valid, use them as the initial center and display a marker
        if (lonInput.value && latInput.value) {
            const lon = Number.parseFloat(lonInput.value)
            const lat = Number.parseFloat(latInput.value)
            if (isLongitude(lon) && isLatitude(lat)) {
                center = L.latLng(lat, lon)
                marker = markerFactory(center)
                // TODO: draggable marker
            }
        }

        // When input is not valid, use the default center
        // This will only focus the map, not display a marker
        if (center === null) {
            const lat = Number.parseFloat(params.lat)
            const lon = Number.parseFloat(params.lon)
            center = L.latLng(lat, lon)
        }

        const zoom = Number.parseInt(params.zoom, 10)
        map.setView(center, zoom)
        map.addEventListener("click", onMapClick)
    })
}
