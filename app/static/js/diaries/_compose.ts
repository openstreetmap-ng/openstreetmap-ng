import i18next, { t } from "i18next"
import * as L from "leaflet"
import { configureStandardForm } from "../_standard-form"
import { isLatitude, isLongitude, zoomPrecision } from "../_utils"
import { getDefaultBaseLayer } from "../leaflet/_layers"
import { type LonLatZoom, getInitialMapState } from "../leaflet/_map-utils"
import { getMarkerIcon } from "../leaflet/_utils"
import { getZoomControl } from "../leaflet/_zoom-control"

const body = document.querySelector("body.diary-compose-body")
if (body) {
    const diaryForm = body.querySelector("form.diary-form")
    configureStandardForm(
        diaryForm,
        ({ redirect_url }) => {
            // On success callback, navigate to the diary
            console.debug("onDiaryFormSuccess", redirect_url)
            window.location.href = redirect_url
        },
        null,
        null,
        { removeEmptyFields: true },
    )

    const showMapContainer = body.querySelector(".show-map-container")
    const lonInput = showMapContainer.querySelector("input[name=lon]")
    const latInput = showMapContainer.querySelector("input[name=lat]")
    const mapDiv = showMapContainer.querySelector("div.leaflet-container")

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

    /** On coordinates input change, update the marker position */
    const onCoordinatesInputChange = () => {
        if (mapDiv.classList.contains("d-none")) return
        if (lonInput.value && latInput.value) {
            const lon = Number.parseFloat(lonInput.value)
            const lat = Number.parseFloat(latInput.value)
            if (isLongitude(lon) && isLatitude(lat)) {
                const latLng = L.latLng(lat, lon)
                // If there's already a marker, move it, otherwise create a new one
                if (marker) marker.setLatLng(latLng)
                else marker = markerFactory(latLng)
                // Focus on the makers if it's offscreen
                if (!map.getBounds().contains(latLng)) {
                    map.setView(latLng)
                }
            }
        }
    }
    lonInput.addEventListener("change", onCoordinatesInputChange)
    latInput.addEventListener("change", onCoordinatesInputChange)

    const showMapButton = showMapContainer.querySelector("button.show-map-btn")
    showMapButton.addEventListener("click", () => {
        // On "Select on map" button click, show the map and hide the button
        showMapButton.classList.add("d-none")
        removeMapButton.classList.remove("d-none")
        mapDiv.classList.remove("d-none")

        if (!map) {
            map = L.map(mapDiv, { zoomControl: false })

            // Disable Leaflet's attribution prefix
            map.attributionControl.setPrefix(false)

            // Add native controls
            map.addControl(getZoomControl())

            // Add default layer
            map.addLayer(getDefaultBaseLayer())
        }

        let state: LonLatZoom | null = null

        // Attempt to parse the lat/lon from the inputs
        // If they're valid, use them as the initial center and display a marker
        if (lonInput.value && latInput.value) {
            const lon = Number.parseFloat(lonInput.value)
            const lat = Number.parseFloat(latInput.value)
            if (isLongitude(lon) && isLatitude(lat)) {
                state = { lon, lat, zoom: 10 }
                marker = markerFactory([lat, lon])
                // TODO: draggable marker
            }
        }

        // When input is not valid, use the default center
        // This will only focus the map, not display a marker
        if (!state) state = getInitialMapState(map)

        map.setView([state.lat, state.lon], state.zoom)
        map.addEventListener("click", onMapClick)
    })

    const removeMapButton = showMapContainer.querySelector("button.remove-location-btn")
    removeMapButton.addEventListener("click", () => {
        // On "Remove location" button click, hide the map and show the button
        showMapButton.classList.remove("d-none")
        removeMapButton.classList.add("d-none")
        mapDiv.classList.add("d-none")

        lonInput.value = ""
        latInput.value = ""
        lonInput.dispatchEvent(new Event("input"))
        latInput.dispatchEvent(new Event("input"))

        marker?.remove()
        marker = null
    })

    const deleteForm = body.querySelector("form.delete-form")
    if (deleteForm) {
        configureStandardForm(deleteForm, ({ redirect_url }) => {
            // On success callback, navigate to my diary
            console.debug("onDeleteFormSuccess", redirect_url)
            window.location.href = redirect_url
        })

        // On delete button click, request confirmation
        const deleteButton = deleteForm.querySelector("button[type=submit]")
        deleteButton.addEventListener("click", (event: Event) => {
            if (!confirm(t("diary.delete_confirmation"))) {
                event.preventDefault()
            }
        })
    }
}
