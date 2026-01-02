import { isLatitude, isLongitude, zoomPrecision } from "@lib/coords"
import { CustomGeolocateControl } from "@lib/map/controls/geolocate"
import { addControlGroup } from "@lib/map/controls/group"
import { CustomZoomControl } from "@lib/map/controls/zoom"
import { configureDefaultMapBehavior } from "@lib/map/defaults"
import {
    addMapLayer,
    addMapLayerSources,
    DEFAULT_LAYER_ID,
} from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import { getInitialMapState, type LonLatZoom } from "@lib/map/state"
import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"
import { assertExists } from "@std/assert"
import { throttle } from "@std/async/unstable-throttle"
import { t } from "i18next"
import { type LngLat, type LngLatLike, Map as MaplibreMap, Marker } from "maplibre-gl"

mount("diary-compose-body", (body) => {
    configureStandardForm(
        body.querySelector("form.diary-form"),
        ({ redirect_url }) => {
            // On success callback, navigate to the diary
            console.debug("DiaryCompose: Success", redirect_url)
            window.location.href = redirect_url
        },
        { removeEmptyFields: true },
    )

    const showMapContainer = body.querySelector(".show-map-container")!
    const lonInput = showMapContainer.querySelector("input[name=lon]")!
    const latInput = showMapContainer.querySelector("input[name=lat]")!
    const mapDiv = showMapContainer.querySelector("div.map-container")!

    let map: MaplibreMap | undefined
    let marker: Marker | null = null

    const setMarker = (lngLat: LngLatLike) => {
        if (marker) {
            marker.setLngLat(lngLat)
            return
        }
        assertExists(map)
        marker = new Marker({
            anchor: MARKER_ICON_ANCHOR,
            element: getMarkerIconElement("red", true),
            draggable: true,
        })
            .setLngLat(lngLat)
            .addTo(map)
        marker.on(
            "drag",
            throttle(
                () => {
                    if (marker) setInput(marker.getLngLat())
                },
                100,
                { ensureLastCall: true },
            ),
        )
    }

    const setInput = (lngLat: LngLat) => {
        assertExists(map)
        const precision = zoomPrecision(map.getZoom())
        const lngLatWrap = lngLat.wrap()
        lonInput.value = lngLatWrap.lng.toFixed(precision)
        latInput.value = lngLatWrap.lat.toFixed(precision)
    }

    /** On map click, update the coordinates and move the marker */
    const onMapClick = ({ lngLat }: { lngLat: LngLat }) => {
        console.debug("DiaryCompose: Map clicked", lngLat.lng, lngLat.lat)
        setMarker(lngLat)
        setInput(lngLat)
    }

    /** On coordinates input change, update the marker position */
    const onCoordinatesInputChange = () => {
        if (mapDiv.classList.contains("d-none")) return
        assertExists(map)

        if (lonInput.value && latInput.value) {
            console.debug(
                "DiaryCompose: Coordinates changed",
                lonInput.value,
                latInput.value,
            )
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

    const showMapButton = showMapContainer.querySelector("button.show-map-btn")!
    const removeMapButton = showMapContainer.querySelector(
        "button.remove-location-btn",
    )!

    /** Toggle map visibility and related UI elements */
    const setMapVisible = (visible: boolean) => {
        showMapButton.classList.toggle("d-none", visible)
        removeMapButton.classList.toggle("d-none", !visible)
        mapDiv.classList.toggle("d-none", !visible)
    }

    showMapButton.addEventListener("click", () => {
        // On "Select on map" button click, show the map and hide the button
        setMapVisible(true)

        if (!map) {
            map = new MaplibreMap({
                container: mapDiv,
                maxZoom: 19,
                attributionControl: { compact: true, customAttribution: "" },
                refreshExpiredTiles: false,
            })
            configureDefaultMapBehavior(map)
            addMapLayerSources(map, DEFAULT_LAYER_ID)
            addControlGroup(map, [
                new CustomZoomControl(),
                new CustomGeolocateControl(),
            ])
            addMapLayer(map, DEFAULT_LAYER_ID)
        }

        let state: LonLatZoom | undefined

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
        state ??= getInitialMapState(map)

        map.jumpTo({
            center: [state.lon, state.lat],
            zoom: state.zoom,
        })
        map.on("click", onMapClick)
    })

    removeMapButton.addEventListener("click", () => {
        // On "Remove location" button click, hide the map and show the button
        setMapVisible(false)

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
            console.debug("DiaryCompose: Deleted", redirect_url)
            window.location.href = redirect_url
        })

        // On delete button click, request confirmation
        const deleteButton = deleteForm.querySelector("button[type=submit]")!
        deleteButton.addEventListener("click", (e) => {
            if (!confirm(t("diary.delete_confirmation"))) {
                e.preventDefault()
            }
        })
    }
})
