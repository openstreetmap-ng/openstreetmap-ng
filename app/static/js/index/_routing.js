import * as L from "leaflet"
import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"
import { getLastRoutingEngine, setLastRoutingEngine } from "../_local-storage.js"
import { qsParse } from "../_qs.js"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { zoomPrecision } from "../_utils.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { GraphHopperEngines } from "./routing-engines/_graphhopper.js"
import { OSRMEngines } from "./routing-engines/_osrm.js"
import { ValhallaEngines } from "./routing-engines/_valhalla.js"

export const routingStyles = {
    route: {
        color: "#0033ff",
        opacity: 0.3,
        weight: 10,
        interactive: false,
    },
    highlight: {
        color: "#ffff00",
        opacity: 0.5,
        weight: 12,
        interactive: false,
    },
}

const dragDataType = "text/osm-marker-guid"
const fromMarkerGuid = "2292de60-aca9-43e1-8bcc-4ca17f517f84"
const toMarkerGuid = "ad4767d0-4f75-4964-986a-697ca1f22c1d"

const routingEngines = new Map([...GraphHopperEngines, ...ValhallaEngines, ...OSRMEngines])

/**
 * Create a new routing controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getRoutingController = (map) => {
    const sidebar = getActionSidebar("directions")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const draggableMarkers = form.querySelectorAll(".draggable-marker")
    const fromInput = form.querySelector("input[name=from]")
    const toInput = form.querySelector("input[name=to]")
    const engineInput = form.querySelector("input[name=engine]") // TODO: load from local storage
    const bboxInput = form.querySelector("input[name=bbox]")
    const reverseButton = form.querySelector(".reverse-button")
    let loaded = false
    let abortController = null

    // Null values until initialized
    let fromMarker = null // green
    let toMarker = null // red
    let routePolyline = null
    let highlightPolyline = null
    let highlightPopup = null // TODO: autoPanPadding: [100, 100]

    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        }).addTo(map)

    const submitFormIfFilled = () => {
        if (fromInput.value && toInput.value) form.submit()
    }

    const callRoutingEngine = () => {
        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()
    }

    /**
     * On marker drag end, update the form's coordinates
     * @param {L.DragEndEvent} event
     * @returns {void}
     */
    const onMarkerDragEnd = (event) => {
        const marker = event.propagatedFrom
        const latLng = marker.getLatLng()
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lon = latLng.lng.toFixed(precision)
        const lat = latLng.lat.toFixed(precision)
        const value = `${lat}, ${lon}`

        if (marker === fromMarker) {
            fromInput.value = value
            fromInput.dispatchEvent(new Event("input"))
        } else if (marker === toMarker) {
            toInput.value = value
            toInput.dispatchEvent(new Event("input"))
        } else {
            console.warn("Unknown routing marker", marker)
        }

        submitFormIfFilled()
    }

    /**
     * On map marker drop, update the marker's coordinates
     * @param {DragEvent} event
     */
    const onMapDrop = (event) => {
        // Skip updates if the sidebar is hidden
        if (!loaded) return

        let marker
        const dragData = event.dataTransfer.getData(dragDataType)
        if (dragData === fromMarkerGuid) {
            if (!fromMarker) {
                fromMarker = markerFactory("green")
                fromMarker.addEventListener("dragend", onMarkerDragEnd)
                map.addLayer(fromMarker)
            }
            marker = fromMarker
        } else if (dragData === toMarkerGuid) {
            if (!toMarker) {
                toMarker = markerFactory("red")
                toMarker.addEventListener("dragend", onMarkerDragEnd)
                map.addLayer(toMarker)
            }
            marker = toMarker
        } else {
            return
        }

        const mousePosition = L.DomEvent.getMousePosition(event, map.getContainer())
        mousePosition.y += 20 // offset position to account for the marker's height

        const latLng = map.containerPointToLatLng(mousePosition)
        marker.setLatLng(latLng)
        marker.fire("dragend", { propagatedFrom: marker })
    }

    // On map update, update the form's bounding box
    const onMapZoomOrMoveEnd = () => {
        // Skip updates if the sidebar is hidden
        if (!loaded) return

        bboxInput.value = map.getBounds().toBBoxString()
    }

    /**
     * On draggable marker drag start, set data and drag image
     * @param {DragEvent} event
     */
    const onDraggableMarkerDragStart = (event) => {
        const target = event.target
        const markerGuid = target.dataset.guid
        console.debug("onDraggableMarkerDragStart", markerGuid)

        const dt = event.dataTransfer
        dt.effectAllowed = "move"
        dt.setData(dragDataType, markerGuid)

        const img = new Image()
        img.src = target.src
        dt.setDragImage(img, 12, 21)
    }

    // On input enter, submit the form
    const onInputEnter = (event) => {
        if (event.key === "Enter") submitFormIfFilled()
    }

    // On engine input change, remember the last routing engine
    const onEngineInputChange = () => {
        setLastRoutingEngine(engineInput.value)
        submitFormIfFilled()
    }

    // On reverse button click, swap the from and to inputs
    const onReverseButtonClick = () => {
        const fromValue = fromInput.value
        fromInput.value = toInput.value
        toInput.value = fromValue
        fromInput.dispatchEvent(new Event("input"))
        toInput.dispatchEvent(new Event("input"))
        submitFormIfFilled()
    }

    // On success callback, call routing engine, display results, and update search params
    const onFormSuccess = ({ from, to, bbox }) => {
        fromInput.value = from.displayName
        toInput.value = to.displayName
        fromInput.dispatchEvent(new Event("input"))
        toInput.dispatchEvent(new Event("input"))

        if (!fromMarker) {
            fromMarker = markerFactory("green")
            fromMarker.addEventListener("dragend", onMarkerDragEnd)
            map.addLayer(fromMarker)
        }

        if (!toMarker) {
            toMarker = markerFactory("red")
            toMarker.addEventListener("dragend", onMarkerDragEnd)
            map.addLayer(toMarker)
        }

        fromMarker.setLatLng(L.latLng(from.lat, from.lon))
        toMarker.setLatLng(L.latLng(to.lat, to.lon))
        callRoutingEngine()

        // Focus on the makers if they're offscreen
        const [minLon, minLat, maxLon, maxLat] = bbox
        const latLngBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
        if (!map.getBounds().contains(latLngBounds)) {
            map.fitBounds(latLngBounds) // TODO: test animate
        }
    }

    // Listen for events
    configureStandardForm(form, onFormSuccess)
    map.addEventListener("drop", onMapDrop)
    map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    for (const draggableMarker of draggableMarkers) {
        draggableMarker.addEventListener("dragstart", onDraggableMarkerDragStart)
    }
    fromInput.addEventListener("input", onInputEnter)
    toInput.addEventListener("input", onInputEnter)
    engineInput.addEventListener("input", onEngineInputChange)
    reverseButton.addEventListener("click", onReverseButtonClick)

    return {
        load: () => {
            form.reset()
            switchActionSidebar("directions")
            document.title = getPageTitle(sidebarTitle)

            // Allow default form setting via URL search parameters
            const searchParams = qsParse(location.search.substring(1))

            if (searchParams.route?.includes(";")) {
                const [from, to] = searchParams.route.split(";")
                fromInput.value = from
                toInput.value = to
                fromInput.dispatchEvent(new Event("input"))
                toInput.dispatchEvent(new Event("input"))
            }

            const routingEngine = getInitialRoutingEngine(searchParams)
            if (routingEngine) {
                if (engineInput.querySelector(`option[value=${routingEngine}]`)) {
                    engineInput.value = routingEngine
                    engineInput.dispatchEvent(new Event("input"))
                } else {
                    console.warn(`Unknown routing engine: ${routingEngine}`)
                }
            }

            loaded = true

            // Initial update to set the inputs
            onMapZoomOrMoveEnd()
            submitFormIfFilled()
        },
        unload: () => {
            if (fromMarker) {
                map.removeLayer(fromMarker)
                fromMarker = null
            }
            if (toMarker) {
                map.removeLayer(toMarker)
                toMarker = null
            }
            if (routePolyline) {
                map.removeLayer(routePolyline)
                routePolyline = null
            }
            if (highlightPolyline) {
                map.removeLayer(highlightPolyline)
                highlightPolyline = null
            }
            if (highlightPopup) map.closePopup(highlightPopup)

            loaded = false
        },
    }
}

/**
 * Get initial routing engine identifier
 * @param {str|undefined} engine Routing engine identifier from search parameters
 * @returns {string|null} Routing engine identifier
 */
const getInitialRoutingEngine = ({ engine }) => {
    return engine ?? getLastRoutingEngine()
}
