import i18next from "i18next"
import * as L from "leaflet"
import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"
import { formatDistance, formatHeight, formatSimpleDistance, formatTime } from "../_format-utils.js"
import { getLastRoutingEngine, setLastRoutingEngine } from "../_local-storage.js"
import { qsParse, qsStringify } from "../_qs.js"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import "../_types.js"
import { zoomPrecision } from "../_utils.js"
import { encodeMapState, getMapState } from "../leaflet/_map-utils.js"
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
const fromMarkerGuid = "018db10c-729f-75cd-a3a9-1beabe239ed0"
const toMarkerGuid = "018db10c-729f-73b8-853d-038e3b39ed0b"

const routingEngines = new Map([...GraphHopperEngines, ...ValhallaEngines, ...OSRMEngines])

/**
 * Create a new routing controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getRoutingController = (map) => {
    const sidebar = getActionSidebar("routing")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const fromInput = form.querySelector("input[name=from]")
    const fromDraggableMarker = form.querySelector(`.draggable-marker[data-guid="${fromMarkerGuid}"]`)
    const toInput = form.querySelector("input[name=to]")
    const toDraggableMarker = form.querySelector(`.draggable-marker[data-guid="${toMarkerGuid}"]`)
    const reverseButton = form.querySelector(".reverse-btn")
    const engineInput = form.querySelector("select[name=engine]")
    const boundsInput = form.querySelector("input[name=bounds]")
    const routeSection = sidebar.querySelector(".section.route")
    const routeDistance = routeSection.querySelector(".route-info .distance")
    const routeTime = routeSection.querySelector(".route-info .time")
    const routeElevationGroup = routeSection.querySelector(".elevation-group")
    const routeAscend = routeElevationGroup.querySelector(".ascend")
    const routeDescend = routeElevationGroup.querySelector(".descend")
    const turnTableBody = routeSection.querySelector(".turn-by-turn tbody")
    const attribution = routeSection.querySelector(".attribution")
    let loaded = true
    let abortController = null

    // Null values until initialized
    let fromMarker = null // green
    let toMarker = null // red
    let routePolyline = null
    let highlightPolyline = null
    let highlightPopup = null // TODO: autoPanPadding: [100, 100]

    // Set default routing engine
    const lastRoutingEngine = getLastRoutingEngine()
    if (routingEngines.has(lastRoutingEngine)) engineInput.value = lastRoutingEngine

    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        }).addTo(map)

    const submitFormIfFilled = () => {
        if (fromInput.value && toInput.value) form.requestSubmit()
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

        const searchParams = qsStringify({
            engine: routingEngineName,
            route: routeParam,
        })
        const hash = encodeMapState(getMapState(map))

        // TODO: will this not remove path?
        history.replaceState(null, "", `?${searchParams}${hash}`)

        // TODO: show loading animation
        routingEngine(abortController.signal, fromCoords, toCoords, onRoutingSuccess, onRoutingError)
    }

    /**
     * On routing success, render the route
     * @param {RoutingRoute} route Route
     * @returns {void}
     */
    const onRoutingSuccess = (route) => {
        console.debug("onRoutingSuccess", route)

        // Display general route information
        const totalDistance = route.steps.reduce((acc, step) => acc + step.distance, 0)
        const totalTime = route.steps.reduce((acc, step) => acc + step.time, 0)
        routeDistance.textContent = formatDistance(totalDistance)
        routeTime.textContent = formatTime(totalTime)

        // Display the optional elevation information
        if (route.ascend !== null && route.descend !== null) {
            routeElevationGroup.classList.remove("d-none")
            routeAscend.textContent = formatHeight(route.ascend)
            routeDescend.textContent = formatHeight(route.descend)
        } else {
            routeElevationGroup.classList.add("d-none")
        }

        // Render the turn-by-turn table
        const newTableBody = document.createElement("tbody")

        let stepNumber = 0
        for (const step of route.steps) {
            stepNumber += 1

            const tr = document.createElement("tr")

            // Icon
            const tdIcon = document.createElement("td")
            tdIcon.classList.add("icon")
            const iconDiv = document.createElement("div")
            iconDiv.classList.add(`icon-${step.code}`)
            tdIcon.appendChild(iconDiv)
            tr.appendChild(tdIcon)

            // Number
            const tdNumber = document.createElement("td")
            tdNumber.classList.add("number")
            tdNumber.textContent = `${stepNumber}.`
            tr.appendChild(tdNumber)

            // Text instruction
            const tdText = document.createElement("td")
            tdText.classList.add("instruction")
            tdText.textContent = step.text
            tr.appendChild(tdText)

            // Distance
            const tdDistance = document.createElement("td")
            tdDistance.classList.add("distance")
            tdDistance.textContent = formatSimpleDistance(step.distance)
            tr.appendChild(tdDistance)

            newTableBody.appendChild(tr)
        }

        turnTableBody.replaceWith(newTableBody)

        attribution.innerHTML = i18next.t("javascripts.directions.instructions.courtesy", {
            link: route.attribution,
            interpolation: { escapeValue: false },
        })
    }

    /**
     * On routing error, display an error message
     * @param {Error} error Error
     * @returns {void}
     */
    const onRoutingError = (error) => {
        // TODO: standard error
        alert(error.message)
    }

    /**
     * On marker drag end, update the form's coordinates
     * @param {L.DragEndEvent} event
     * @returns {void}
     */
    const onMarkerDragEnd = (event) => {
        console.debug("onMarkerDragEnd", event)

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
     * On map marker drop, update the marker's coordinates
     * @param {DragEvent} event
     */
    const onMapDrop = (event) => {
        // Skip updates if the sidebar is hidden
        if (!loaded) return

        let marker
        const dragData = event.dataTransfer.getData(dragDataType)
        console.debug("onMapDrop", dragData)

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

        // TODO: handle 180th meridian
        boundsInput.value = map.getBounds().toBBoxString()
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
        dt.setData("text/plain", "")
        dt.setData(dragDataType, markerGuid)

        const canvas = document.createElement("canvas")
        canvas.width = 25
        canvas.height = 41

        const ctx = canvas.getContext("2d")
        ctx.drawImage(target, 0, 0, 25, 41)
        dt.setDragImage(canvas, 12, 21)
    }

    // On input enter, submit the form
    const onInput = (event) => {
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
    const onFormSuccess = ({ from, to, bounds }) => {
        console.debug("onFormSuccess", from, to, bounds)

        fromInput.value = from.name
        toInput.value = to.name
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

        const [fromLon, fromLat] = from.point
        const [toLon, toLat] = to.point
        fromMarker.setLatLng(L.latLng(fromLat, fromLon))
        toMarker.setLatLng(L.latLng(toLat, toLon))
        callRoutingEngine()

        // Focus on the makers if they're offscreen
        const [minLon, minLat, maxLon, maxLat] = bounds
        const latLngBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
        if (!map.getBounds().contains(latLngBounds)) {
            map.fitBounds(latLngBounds)
        }
    }

    // Listen for events
    configureStandardForm(form, onFormSuccess)
    const mapContainer = map.getContainer()
    mapContainer.addEventListener("dragover", (event) => event.preventDefault())
    mapContainer.addEventListener("drop", onMapDrop)
    map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    fromInput.addEventListener("input", onInput)
    fromDraggableMarker.addEventListener("dragstart", onDraggableMarkerDragStart)
    toInput.addEventListener("input", onInput)
    toDraggableMarker.addEventListener("dragstart", onDraggableMarkerDragStart)
    reverseButton.addEventListener("click", onReverseButtonClick)
    engineInput.addEventListener("input", onEngineInputChange)

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
