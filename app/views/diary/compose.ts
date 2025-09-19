import i18next from "i18next"
import { type LngLat, type LngLatLike, Map as MaplibreMap, Marker } from "maplibre-gl"
import { CustomGeolocateControl } from "../lib/map/controls/geolocate"
import { CustomZoomControl } from "../lib/map/controls/zoom"
import {
    addMapLayer,
    addMapLayerSources,
    defaultLayerId,
} from "../lib/map/layers/layers"
import {
    addControlGroup,
    getInitialMapState,
    type LonLatZoom,
} from "../lib/map/map-utils"
import {
    configureDefaultMapBehavior,
    getMarkerIconElement,
    markerIconAnchor,
} from "../lib/map/utils"
import { mount } from "../lib/mount"
import { configureStandardForm } from "../lib/standard-form"
import { isLatitude, isLongitude, throttle, zoomPrecision } from "../lib/utils"

mount("diary-compose-body", (body) => {
    configureStandardForm(
        body.querySelector("form.diary-form"),
        ({ redirect_url }) => {
            // On success callback, navigate to the diary
            console.debug("onDiaryFormSuccess", redirect_url)
            window.location.href = redirect_url
        },
        { removeEmptyFields: true },
    )

    const showMapContainer = body.querySelector(".show-map-container")
    const lonInput = showMapContainer.querySelector("input[name=lon]")
    const latInput = showMapContainer.querySelector("input[name=lat]")
    const mapDiv = showMapContainer.querySelector("div.map-container")

    let map: MaplibreMap | null = null
    let marker: Marker | null = null

    const setMarker = (lngLat: LngLatLike): void => {
        if (marker) {
            marker.setLngLat(lngLat)
            return
        }
        marker = new Marker({
            anchor: markerIconAnchor,
            element: getMarkerIconElement("red", true),
            draggable: true,
        })
            .setLngLat(lngLat)
            .addTo(map)
        marker.on(
            "drag",
            throttle(() => setInput(marker.getLngLat()), 100),
        )
    }

    const setInput = (lngLat: LngLat): void => {
        const precision = zoomPrecision(map.getZoom())
        const lngLatWrap = lngLat.wrap()
        lonInput.value = lngLatWrap.lng.toFixed(precision)
        latInput.value = lngLatWrap.lat.toFixed(precision)
    }

    /** On map click, update the coordinates and move the marker */
    const onMapClick = ({ lngLat }: { lngLat: LngLat }) => {
        console.debug("onMapClick", lngLat.lng, lngLat.lat)
        setMarker(lngLat)
        setInput(lngLat)
    }

    /** On coordinates input change, update the marker position */
    const onCoordinatesInputChange = () => {
        if (mapDiv.classList.contains("d-none")) return
        if (lonInput.value && latInput.value) {
            console.debug("onCoordinatesInputChange", lonInput.value, latInput.value)
            const lon = Number.parseFloat(lonInput.value)
            const lat = Number.parseFloat(latInput.value)
            if (isLongitude(lon) && isLatitude(lat)) {
                const lngLat: LngLatLike = [lon, lat]
                setMarker(lngLat)
                // Focus on the makers if it's offscreen
                if (!map.getBounds().contains(lngLat)) {
                    map.panTo(lngLat)
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
                attributionControl: { compact: true, customAttribution: "" },
                refreshExpiredTiles: false,
            })
            configureDefaultMapBehavior(map)
            addMapLayerSources(map, defaultLayerId)
            addControlGroup(map, [
                new CustomZoomControl(),
                new CustomGeolocateControl(),
            ])
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
                setMarker([lon, lat])
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
})
