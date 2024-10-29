import * as L from "leaflet"
import { zoomPrecision } from "./_utils"
import { getGeolocateControl } from "./leaflet/_geolocate-control"
import { getDefaultBaseLayer } from "./leaflet/_layers"
import { type LonLat, addControlGroup } from "./leaflet/_map-utils"
import { getMarkerIcon } from "./leaflet/_utils"
import { getZoomControl } from "./leaflet/_zoom-control"

const defaultHomeZoom = 12

const userSettingsForm = document.querySelector("form.user-settings-form")
if (userSettingsForm) {
    const lonInput = userSettingsForm.elements.namedItem("home_longitude") as HTMLInputElement
    const latInput = userSettingsForm.elements.namedItem("home_latitude") as HTMLInputElement
    const mapDiv = userSettingsForm.querySelector("div.leaflet-container")
    const map = L.map(mapDiv, {
        attributionControl: false,
        zoomControl: false,
        center: L.latLng(0, 0),
        zoom: 1,
    })

    // TODO: draggable marker
    // TODO: icon licenses

    // Add default layer
    map.addLayer(getDefaultBaseLayer())

    // Add custom zoom and location controls
    addControlGroup(map, [getZoomControl(), getGeolocateControl()])

    // Null value until the marker is initialized
    let marker: L.Marker | null = null
    let restorePoint: LonLat | null = null

    const markerFactory = (latLng: L.LatLngExpression): L.Marker =>
        L.marker(latLng, {
            icon: getMarkerIcon("blue-home", true), // TODO: revise icon
            keyboard: false,
            interactive: false,
        }).addTo(map)

    // Set initial view
    if (lonInput.value && latInput.value) {
        const lon = Number.parseFloat(lonInput.value)
        const lat = Number.parseFloat(latInput.value)
        const latLng = L.latLng(lat, lon)
        map.setView(latLng, defaultHomeZoom)
        marker = markerFactory(latLng)
    }

    /** On map click, update the coordinates and move the marker */
    const onMapClick = ({ latlng }: { latlng: L.LatLng }) => {
        const precision = zoomPrecision(map.getZoom())
        const lon = latlng.lng.toFixed(precision)
        const lat = latlng.lat.toFixed(precision)
        const latLng = L.latLng(Number(lat), Number(lon))

        lonInput.value = lon
        latInput.value = lat

        // If there's already a marker, move it, otherwise create a new one
        if (marker) marker.setLatLng(latLng)
        else marker = markerFactory(latLng)
    }

    // TODO: make those leaflet buttons
    // On delete click, remember restore point, remove coordinates and toggle buttons visibility
    const deleteButton = userSettingsForm.querySelector("button.home-delete-btn")
    deleteButton.addEventListener("click", () => {
        map.removeLayer(marker)
        marker = null
        restorePoint = {
            lon: Number.parseFloat(lonInput.value),
            lat: Number.parseFloat(latInput.value),
        }
        lonInput.value = ""
        latInput.value = ""
        deleteButton.classList.add("d-none")
        restoreButton.classList.remove("d-none")
    })

    // On restore click, restore coordinates and toggle buttons visibility
    const restoreButton = userSettingsForm.querySelector("button.home-restore-btn")
    restoreButton.addEventListener("click", () => {
        onMapClick({ latlng: L.latLng(restorePoint.lat, restorePoint.lon) })
        restorePoint = null
        deleteButton.classList.remove("d-none")
        restoreButton.classList.add("d-none")
    })

    map.addEventListener("click", onMapClick)
}
