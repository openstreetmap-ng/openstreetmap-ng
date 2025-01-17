import i18next from "i18next"
import { type LngLatLike, Map as MaplibreMap, type MapMouseEvent, Marker, NavigationControl, Popup } from "maplibre-gl"
import { configureStandardForm } from "../_standard-form"
import { isLatitude, isLongitude, zoomPrecision } from "../_utils"
import { addMapLayer, addMapLayerSources, defaultLayerId } from "../leaflet/_layers.ts"
import { getInitialMapState, type LonLatZoom } from "../leaflet/_map-utils"
import { disableMapRotation, getMarkerIconElement, markerIconAnchor } from "../leaflet/_utils.ts"

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

    let map: MaplibreMap | null = null
    let marker: Marker | null = null

    const markerFactory = (lngLat: LngLatLike) =>
        new Marker({
            anchor: markerIconAnchor,
            element: getMarkerIconElement("red", true),
        })
            .setLngLat(lngLat)
            .setPopup(new Popup().setText(i18next.t("diary_entries.edit.marker_text")))
            .addTo(map)

    /** On map click, update the coordinates and move the marker */
    const onMapClick = (e: MapMouseEvent) => {
        const precision = zoomPrecision(map.getZoom())
        const lon = e.lngLat.lng.toFixed(precision)
        const lat = e.lngLat.lat.toFixed(precision)

        lonInput.value = lon
        latInput.value = lat

        const lngLat: LngLatLike = [Number(lon), Number(lat)]
        // If there's already a marker, move it, otherwise create a new one
        if (marker) marker.setLngLat(lngLat)
        else marker = markerFactory(lngLat)
    }

    /** On coordinates input change, update the marker position */
    const onCoordinatesInputChange = () => {
        if (mapDiv.classList.contains("d-none")) return
        if (lonInput.value && latInput.value) {
            const lon = Number.parseFloat(lonInput.value)
            const lat = Number.parseFloat(latInput.value)
            if (isLongitude(lon) && isLatitude(lat)) {
                const lngLag: LngLatLike = [lon, lat]
                // If there's already a marker, move it, otherwise create a new one
                if (marker) marker.setLngLat(lngLag)
                else marker = markerFactory(lngLag)
                // Focus on the makers if it's offscreen
                if (!map.getBounds().contains(lngLag)) {
                    map.panTo(lngLag)
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
            map = new MaplibreMap({
                container: mapDiv,
                maxZoom: 19,
                attributionControl: false,
            })
            disableMapRotation(map)
            addMapLayerSources(map, "base")
            map.addControl(new NavigationControl({ showCompass: false }))
            addMapLayer(map, defaultLayerId)
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

        map.jumpTo({
            center: [state.lon, state.lat],
            zoom: state.zoom,
        })
        map.on("click", onMapClick)
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
            if (!confirm(i18next.t("diary.delete_confirmation"))) {
                event.preventDefault()
            }
        })
    }
}
