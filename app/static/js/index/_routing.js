import i18next from "i18next"
import * as L from "leaflet"
import { formatDistance, formatHeight, formatSimpleDistance, formatTime } from "../_format-utils.js"
import { getLastRoutingEngine, setLastRoutingEngine } from "../_local-storage.js"
import { qsParse } from "../_qs.js"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import "../_types.js"
import { zoomPrecision } from "../_utils.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"
import { GraphHopperEngines } from "./routing-engines/_graphhopper.js"
import { OSRMEngines } from "./routing-engines/_osrm.js"
import { ValhallaEngines } from "./routing-engines/_valhalla.js"

export const styles = {
    default: {
        pane: "routing",
        color: "#0033ff",
        opacity: 0.3,
        weight: 10,
        interactive: false,
    },
    hover: {
        pane: "routing",
        color: "#ffff00",
        opacity: 0,
        weight: 10,
        interactive: true,
    },
    hoverActive: {
        opacity: 0.5,
    },
}

const dragDataType = "text/osm-routing-direction"

const routingEngines = new Map([...GraphHopperEngines, ...ValhallaEngines, ...OSRMEngines])

let paneCreated = false

/**
 * Create a new routing controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getRoutingController = (map) => {
    const mapContainer = map.getContainer()
    const routingLayer = getOverlayLayerById("routing")
    const sidebar = getActionSidebar("routing")
    const parentSidebar = sidebar.closest(".sidebar")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const fromInput = form.elements.from
    const fromLoadedInput = form.elements.from_loaded
    const fromDraggableMarker = form.querySelector(".draggable-marker[data-direction=from]")
    const toInput = form.elements.to
    const toLoadedInput = form.elements.to_loaded
    const toDraggableMarker = form.querySelector(".draggable-marker[data-direction=to]")
    const reverseButton = form.querySelector(".reverse-btn")
    const engineInput = form.elements.engine
    const bboxInput = form.elements.bbox
    const loadingContainer = sidebar.querySelector(".loading")
    const routingErrorAlert = sidebar.querySelector(".routing-error-alert")
    const routeContainer = sidebar.querySelector(".route")
    const routeDistance = routeContainer.querySelector(".route-info .distance")
    const routeTime = routeContainer.querySelector(".route-info .time")
    const routeElevationContainer = routeContainer.querySelector(".route-elevation-info")
    const routeAscend = routeElevationContainer.querySelector(".ascend")
    const routeDescend = routeElevationContainer.querySelector(".descend")
    const stepsTableBody = routeContainer.querySelector(".route-steps tbody")
    const attribution = routeContainer.querySelector(".attribution")
    const popupTemplate = routeContainer.querySelector("template.popup")
    const stepTemplate = routeContainer.querySelector("template.step")
    let abortController = null

    // Null values until initialized
    let fromBounds = null
    let fromMarker = null
    let toBounds = null
    let toMarker = null

    const popup = L.popup({
        autoPanPadding: [80, 80],
        bubblingMouseEvents: false,
        className: "route-steps",
    })

    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        }).addTo(map)

    /**
     * On draggable marker drag start, set data and drag image
     * @param {DragEvent} event
     */
    const onInterfaceMarkerDragStart = (event) => {
        const target = event.target
        const direction = target.dataset.direction
        console.debug("onInterfaceMarkerDragStart", direction)

        const dt = event.dataTransfer
        dt.effectAllowed = "move"
        dt.setData("text/plain", "")
        dt.setData(dragDataType, direction)
        const canvas = document.createElement("canvas")
        canvas.width = 25
        canvas.height = 41
        const ctx = canvas.getContext("2d")
        ctx.drawImage(target, 0, 0, 25, 41)
        dt.setDragImage(canvas, 12, 21)
    }

    /**
     * On marker drag end, update the form's coordinates
     * @param {L.DragEndEvent} event
     * @returns {void}
     */
    const onMapMarkerDragEnd = (event) => {
        console.debug("onMapMarkerDragEnd", event)

        const marker = event.propagatedFrom || event.target
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
     * On map drag over, prevent default behavior
     * @param {DragEvent} event
     */
    const onMapDragOver = (event) => event.preventDefault()

    /**
     * On map marker drop, update the marker's coordinates
     * @param {DragEvent} event
     */
    const onMapDrop = (event) => {
        let marker
        const dragData = event.dataTransfer.getData(dragDataType)
        console.debug("onMapDrop", dragData)

        if (dragData === "from") {
            if (!fromMarker) {
                fromMarker = markerFactory("green")
                fromMarker.addEventListener("dragend", onMapMarkerDragEnd)
                map.addLayer(fromMarker)
            }
            marker = fromMarker
        } else if (dragData === "to") {
            if (!toMarker) {
                toMarker = markerFactory("red")
                toMarker.addEventListener("dragend", onMapMarkerDragEnd)
                map.addLayer(toMarker)
            }
            marker = toMarker
        } else {
            return
        }

        const mousePosition = L.DomEvent.getMousePosition(event, mapContainer)
        mousePosition.y += 20 // offset position to account for the marker's height
        const latLng = map.containerPointToLatLng(mousePosition)
        marker.setLatLng(latLng)
        marker.fire("dragend", { propagatedFrom: marker })
    }

    // On map update, update the form's bounding box
    const onMapZoomOrMoveEnd = () => {
        bboxInput.value = map.getBounds().toBBoxString()
    }

    // On engine input change, remember the last routing engine
    const onEngineInputChange = () => {
        setLastRoutingEngine(engineInput.value)
        submitFormIfFilled()
    }

    // On reverse button click, swap the from and to inputs
    const onReverseButtonClick = () => {
        const newFromValue = toInput.value
        const newToValue = fromInput.value
        fromInput.value = newFromValue
        fromInput.dispatchEvent(new Event("input"))
        toInput.value = newToValue
        toInput.dispatchEvent(new Event("input"))
        if (
            fromMarker &&
            toMarker &&
            fromInput.value === fromLoadedInput.value &&
            toInput.value === toLoadedInput.value
        ) {
            const newFromLatLng = toMarker.getLatLng()
            const newToLatLng = fromMarker.getLatLng()
            fromMarker.setLatLng(newFromLatLng)
            fromLoadedInput.value = newFromValue
            toMarker.setLatLng(newToLatLng)
            toLoadedInput.value = newToValue
        }
        submitFormIfFilled()
    }

    const submitFormIfFilled = () => {
        map.closePopup(popup)
        if (fromInput.value && toInput.value) form.requestSubmit()
    }

    // On client validation, hide previous route data
    const onClientValidation = () => {
        routingErrorAlert.classList.add("d-none")
        routeContainer.classList.add("d-none")
    }

    // On success callback, call routing engine, display results, and update search params
    const onFormSuccess = (data) => {
        console.debug("onFormSuccess", data)

        if (data.from) {
            const { bounds, geom, name } = data.from
            fromBounds = L.latLngBounds(L.latLng(bounds[1], bounds[0]), L.latLng(bounds[3], bounds[2]))
            fromInput.value = name
            fromInput.dispatchEvent(new Event("input"))
            if (!fromMarker) {
                fromMarker = markerFactory("green")
                fromMarker.addEventListener("dragend", onMapMarkerDragEnd)
                map.addLayer(fromMarker)
            }
            const [lon, lat] = geom
            fromMarker.setLatLng(L.latLng(lat, lon))
            fromLoadedInput.value = name
        }

        if (data.to) {
            const { bounds, geom, name } = data.to
            toBounds = L.latLngBounds(L.latLng(bounds[1], bounds[0]), L.latLng(bounds[3], bounds[2]))
            toInput.value = name
            toInput.dispatchEvent(new Event("input"))
            if (!toMarker) {
                toMarker = markerFactory("red")
                toMarker.addEventListener("dragend", onMapMarkerDragEnd)
                map.addLayer(toMarker)
            }
            const [lon, lat] = geom
            toMarker.setLatLng(L.latLng(lat, lon))
            toLoadedInput.value = name
        }

        // Focus on the makers if they're offscreen
        const markerBounds = fromBounds.extend(toBounds)
        if (!map.getBounds().contains(markerBounds)) {
            map.fitBounds(markerBounds)
        }

        callRoutingEngine()
    }

    const callRoutingEngine = () => {
        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const routingEngineName = engineInput.value
        const routingEngine = routingEngines.get(routingEngineName)
        const fromLatLng = fromMarker.getLatLng()
        const fromCoords = { lon: fromLatLng.lng, lat: fromLatLng.lat }
        const toLatLng = toMarker.getLatLng()
        const toCoords = { lon: toLatLng.lng, lat: toLatLng.lat }

        // Remember routing configuration in URL search params
        const precision = zoomPrecision(19)
        const fromRouteParam = `${fromCoords.lat.toFixed(precision)},${fromCoords.lon.toFixed(precision)}`
        const toRouteParam = `${toCoords.lat.toFixed(precision)},${toCoords.lon.toFixed(precision)}`
        const routeParam = `${fromRouteParam};${toRouteParam}`

        const url = new URL(location.href)
        url.searchParams.set("engine", routingEngineName)
        url.searchParams.set("route", routeParam)
        window.history.replaceState(null, "", url)

        loadingContainer.classList.remove("d-none")
        routingEngine(abortController.signal, fromCoords, toCoords, onRoutingSuccess, onRoutingError)
    }

    /**
     * On routing success, render the route
     * @param {RoutingRoute} route Route
     * @returns {void}
     */
    const onRoutingSuccess = (route) => {
        console.debug("onRoutingSuccess", route)
        loadingContainer.classList.add("d-none")

        // Display general route information
        const totalDistance = route.steps.reduce((acc, step) => acc + step.distance, 0)
        const totalTime = route.steps.reduce((acc, step) => acc + step.time, 0)
        routeDistance.textContent = formatDistance(totalDistance)
        routeTime.textContent = formatTime(totalTime)

        // Display the optional elevation information
        if (route.ascend !== null && route.descend !== null) {
            routeElevationContainer.classList.remove("d-none")
            routeAscend.textContent = formatHeight(route.ascend)
            routeDescend.textContent = formatHeight(route.descend)
        } else {
            routeElevationContainer.classList.add("d-none")
        }

        // Render the turn-by-turn table
        const fragment = document.createDocumentFragment()
        const layers = []

        // Create a single geometry for the route
        const fullGeom = []
        if (route.steps.length) {
            for (const step of route.steps) {
                fullGeom.push(...step.geom)
            }
            layers.push(L.polyline(fullGeom, styles.default))
        }

        let stepNumber = 0
        for (const step of route.steps) {
            stepNumber += 1
            const div = stepTemplate.content.cloneNode(true).children[0]
            div.querySelector(".icon div").classList.add(`icon-${step.code}`)
            div.querySelector(".number").textContent = `${stepNumber}.`
            div.querySelector(".instruction").textContent = step.text
            div.querySelector(".distance").textContent = formatSimpleDistance(step.distance)
            fragment.appendChild(div)

            const layer = L.polyline(step.geom, styles.hover)
            layers.push(layer)

            // On mouseover, scroll result into view and focus the fragment
            const onMouseover = () => {
                const sidebarRect = parentSidebar.getBoundingClientRect()
                const resultRect = div.getBoundingClientRect()
                const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
                if (!isVisible) div.scrollIntoView({ behavior: "smooth", block: "center" })

                div.classList.add("hover")
                layer.setStyle(styles.hoverActive)
            }

            // On mouseout, unfocus the fragment
            const onMouseout = () => {
                div.classList.remove("hover")
                layer.setStyle(styles.hover)
            }

            // On click, show the popup
            const onClick = () => {
                const content = popupTemplate.content.children[0]
                content.querySelector(".number").innerHTML = div.querySelector(".number").innerHTML
                content.querySelector(".instruction").innerHTML = div.querySelector(".instruction").innerHTML
                popup.setContent(content.innerHTML)
                const latLng = L.latLng(step.geom[0])
                popup.setLatLng(latLng)
                map.openPopup(popup)
            }

            // Listen for events
            div.addEventListener("mouseover", onMouseover)
            div.addEventListener("mouseout", onMouseout)
            div.addEventListener("click", onClick)
            layer.addEventListener("mouseover", onMouseover)
            layer.addEventListener("mouseout", onMouseout)
            layer.addEventListener("click", onClick)
        }

        stepsTableBody.innerHTML = ""
        stepsTableBody.appendChild(fragment)
        attribution.innerHTML = i18next.t("javascripts.directions.instructions.courtesy", {
            link: route.attribution,
            interpolation: { escapeValue: false },
        })
        routeContainer.classList.remove("d-none")

        routingLayer.clearLayers()
        routingLayer.addLayer(L.layerGroup(layers))
        console.debug("Route showing", route.steps.length, "steps")
    }

    /**
     * On routing error, display an error message
     * @param {Error} error Error
     * @returns {void}
     */
    const onRoutingError = (error) => {
        loadingContainer.classList.add("d-none")
        routingErrorAlert.querySelector("p").textContent = error.message
        routingErrorAlert.classList.remove("d-none")
    }

    configureStandardForm(form, onFormSuccess, onClientValidation)

    return {
        load: () => {
            // Listen for events
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            mapContainer.addEventListener("dragover", onMapDragOver)
            mapContainer.addEventListener("drop", onMapDrop)
            fromDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)
            toDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)
            reverseButton.addEventListener("click", onReverseButtonClick)
            engineInput.addEventListener("input", onEngineInputChange)

            // Create the routing layer if it doesn't exist
            if (!map.hasLayer(routingLayer)) {
                if (!paneCreated) {
                    console.debug("Creating routing pane")
                    map.createPane("routing")
                    paneCreated = true
                }

                console.debug("Adding overlay layer", routingLayer.options.layerId)
                map.addLayer(routingLayer)
                map.fire("overlayadd", { layer: routingLayer, name: routingLayer.options.layerId })
            }

            switchActionSidebar(map, "routing")
            document.title = getPageTitle(sidebarTitle)

            // Initial update to set the inputs
            onMapZoomOrMoveEnd()

            // Allow default form setting via URL search parameters
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.route?.includes(";")) {
                const [from, to] = searchParams.route.split(";")
                fromInput.value = from
                fromInput.dispatchEvent(new Event("input"))
                toInput.value = to
                toInput.dispatchEvent(new Event("input"))
            }

            if (searchParams.from) {
                fromInput.value = searchParams.from
                fromInput.dispatchEvent(new Event("input"))
            }
            if (searchParams.to) {
                toInput.value = searchParams.to
                toInput.dispatchEvent(new Event("input"))
            }
            const routingEngine = getInitialRoutingEngine(searchParams)
            if (routingEngine) {
                if (engineInput.querySelector(`option[value=${routingEngine}]`)) {
                    engineInput.value = routingEngine
                    engineInput.dispatchEvent(new Event("input"))
                } else {
                    console.warn("Unsupported routing engine", routingEngine)
                }
            }
        },
        unload: () => {
            // Remove the routing layer
            if (map.hasLayer(routingLayer)) {
                console.debug("Removing overlay layer", routingLayer.options.layerId)
                map.removeLayer(routingLayer)
                map.fire("overlayremove", { layer: routingLayer, name: routingLayer.options.layerId })
            }

            // Clear the routing layer
            routingLayer.clearLayers()

            map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            mapContainer.removeEventListener("dragover", onMapDragOver)
            mapContainer.removeEventListener("drop", onMapDrop)
            fromDraggableMarker.removeEventListener("dragstart", onInterfaceMarkerDragStart)
            toDraggableMarker.removeEventListener("dragstart", onInterfaceMarkerDragStart)
            reverseButton.removeEventListener("click", onReverseButtonClick)
            engineInput.removeEventListener("input", onEngineInputChange)

            loadingContainer.classList.add("d-none")
            routingErrorAlert.classList.add("d-none")
            routeContainer.classList.add("d-none")

            if (fromMarker) {
                map.removeLayer(fromMarker)
                fromMarker = null
                fromLoadedInput.value = ""
            }
            if (toMarker) {
                map.removeLayer(toMarker)
                toMarker = null
                toLoadedInput.value = ""
            }

            map.closePopup(popup)
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
