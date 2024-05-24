import * as L from "leaflet"
import { zoomPrecision } from "./_utils.js"
import { getGeolocateControl } from "./leaflet/_geolocate-control.js"
import { getBaseLayerById, getLayerIdByCode } from "./leaflet/_layers.js"
import { getMarkerIcon } from "./leaflet/_utils.js"
import { getZoomControl } from "./leaflet/_zoom-control.js"

const defaultHomeZoom = 12

const userSettingsForm = document.querySelector(".user-settings-form")
if (userSettingsForm) {
    const lonInput = userSettingsForm.elements.home_longitude
    const latInput = userSettingsForm.elements.home_latitude
    // TODO: make those leaflet buttons
    const deleteButton = userSettingsForm.querySelector(".home-delete-btn")
    const restoreButton = userSettingsForm.querySelector(".home-restore-btn")
    const mapDiv = userSettingsForm.querySelector(".leaflet-container")

    const map = L.map(mapDiv, {
        attributionControl: false,
        zoomControl: false,
        center: L.latLng(0, 0),
        zoom: 1,
    })

    // TODO: draggable marker
    // TODO: icon licenses

    // Add default layer
    map.addLayer(getBaseLayerById(getLayerIdByCode("")))

    // Add custom zoom and location controls
    map.addControl(getZoomControl())
    map.addControl(getGeolocateControl())

    // Null value until the marker is initialized
    let marker = null
    let restorePoint = null

    const markerFactory = (latLng) =>
        L.marker(latLng, {
            icon: getMarkerIcon("blue-home", true),
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

    // On delete click, remember restore point, remove coordinates and toggle buttons visibility
    const onDeleteButtonClick = () => {
        map.removeLayer(marker)
        marker = null
        restorePoint = {
            lon: lonInput.value,
            lat: latInput.value,
        }
        lonInput.value = ""
        latInput.value = ""
        deleteButton.classList.add("d-none")
        restoreButton.classList.remove("d-none")
    }

    // On restore click, restore coordinates and toggle buttons visibility
    const onRestoreButtonClick = () => {
        onMapClick({ latlng: L.latLng(restorePoint.lat, restorePoint.lon) })
        restorePoint = null
        deleteButton.classList.remove("d-none")
        restoreButton.classList.add("d-none")
    }

    // Listen for events
    map.addEventListener("click", onMapClick)
    deleteButton.addEventListener("click", onDeleteButtonClick)
    restoreButton.addEventListener("click", onRestoreButtonClick)
}
