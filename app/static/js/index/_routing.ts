import i18next from "i18next"
import * as L from "leaflet"
import { formatDistance, formatDistanceRounded, formatHeight, formatTime } from "../_format-utils"
import { getLastRoutingEngine, setLastRoutingEngine } from "../_local-storage"
import { qsParse } from "../_qs"
import { configureStandardForm } from "../_standard-form"
import { getPageTitle } from "../_title"
import type { Bounds } from "../_types"
import { zoomPrecision } from "../_utils"
import { type LayerId, getOverlayLayerById } from "../leaflet/_layers"
import type { LonLat } from "../leaflet/_map-utils"
import { getMarkerIcon } from "../leaflet/_utils"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"
import { GraphHopperEngines } from "./routing-engines/_graphhopper"
import { OSRMEngines } from "./routing-engines/_osrm"
import { ValhallaEngines } from "./routing-engines/_valhalla"

export interface RoutingStep {
    geom: [number, number][]
    distance: number
    time: number
    code: number
    text: string
}

export interface RoutingRoute {
    steps: RoutingStep[]
    attribution: string
    ascend?: number
    descend?: number
}

export type RoutingEngine = (
    abortSignal: AbortSignal,
    from: LonLat,
    to: LonLat,
    successCallback: (route: RoutingRoute) => void,
    errorCallback: (error: Error) => void,
) => void

const styles: { [key: string]: L.PolylineOptions } = {
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
const routingLayerId = "routing" as LayerId
const routingEngines: Map<string, RoutingEngine> = new Map([...GraphHopperEngines, ...ValhallaEngines, ...OSRMEngines])
let paneCreated = false

/** Create a new routing controller */
export const getRoutingController = (map: L.Map): IndexController => {
    const mapContainer = map.getContainer()
    const routingLayer = getOverlayLayerById(routingLayerId) as L.FeatureGroup
    const sidebar = getActionSidebar("routing")
    const parentSidebar = sidebar.closest(".sidebar")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form")
    const fromInput = form.elements.namedItem("from") as HTMLInputElement
    const fromLoadedInput = form.elements.namedItem("from_loaded") as HTMLInputElement
    const fromDraggableMarker = form.querySelector("img.draggable-marker[data-direction=from]")
    const toInput = form.elements.namedItem("to") as HTMLInputElement
    const toLoadedInput = form.elements.namedItem("to_loaded") as HTMLInputElement
    const toDraggableMarker = form.querySelector("img.draggable-marker[data-direction=to]")
    const reverseButton = form.querySelector("button.reverse-btn")
    const engineInput = form.elements.namedItem("engine") as HTMLInputElement
    const bboxInput = form.elements.namedItem("bbox") as HTMLInputElement
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

    let abortController: AbortController | null = null
    let fromBounds: L.LatLngBounds | null = null
    let fromMarker: L.Marker | null = null
    let toBounds: L.LatLngBounds | null = null
    let toMarker: L.Marker | null = null

    const popup = L.popup({
        className: "route-steps",
        autoPanPadding: [80, 80],
        // @ts-ignore
        bubblingMouseEvents: false,
    })

    const markerFactory = (color: string): L.Marker =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        }).addTo(map)

    /** On draggable marker drag start, set data and drag image */
    const onInterfaceMarkerDragStart = (event: DragEvent) => {
        const target = event.target as HTMLImageElement
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
    fromDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)
    toDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)

    /** On marker drag end, update the form's coordinates */
    const onMapMarkerDragEnd = (event: L.DragEndEvent): void => {
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

    /** On map drag over, prevent default behavior */
    const onMapDragOver = (event: DragEvent) => event.preventDefault()

    /** On map marker drop, update the marker's coordinates */
    const onMapDrop = (event: DragEvent) => {
        const dragData = event.dataTransfer.getData(dragDataType)
        console.debug("onMapDrop", dragData)

        let marker: L.Marker
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

    /** On map update, update the form's bounding box */
    const onMapZoomOrMoveEnd = () => {
        bboxInput.value = map.getBounds().toBBoxString()
    }

    // On engine input change, remember the last routing engine
    engineInput.addEventListener("input", () => {
        console.debug("onEngineInputChange")
        setLastRoutingEngine(engineInput.value)
        submitFormIfFilled()
    })

    // On reverse button click, swap the from and to inputs
    reverseButton.addEventListener("click", () => {
        console.debug("onReverseButtonClick")
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
    })

    /** Utility method to submit the form if filled with data */
    const submitFormIfFilled = () => {
        map.closePopup(popup)
        if (fromInput.value && toInput.value) form.requestSubmit()
    }

    configureStandardForm(
        form,
        (data) => {
            // On success callback, call routing engine, display results, and update search params
            console.debug("onFormSuccess", data)

            if (data.from) {
                const { bounds, geom, name }: { bounds: Bounds; geom: [number, number]; name: string } = data.from
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
                const { bounds, geom, name }: { bounds: Bounds; geom: [number, number]; name: string } = data.to
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
        },
        () => {
            // On client validation, hide previous route data
            routingErrorAlert.classList.add("d-none")
            routeContainer.classList.add("d-none")
            return null
        },
    )

    const callRoutingEngine = () => {
        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const routingEngineName = engineInput.value
        const routingEngine = routingEngines.get(routingEngineName)
        const fromLatLng = fromMarker.getLatLng()
        const fromCoords: LonLat = { lon: fromLatLng.lng, lat: fromLatLng.lat }
        const toLatLng = toMarker.getLatLng()
        const toCoords: LonLat = { lon: toLatLng.lng, lat: toLatLng.lat }

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

    /** On routing success, render the route */
    const onRoutingSuccess = (route: RoutingRoute): void => {
        console.debug("onRoutingSuccess", route)
        loadingContainer.classList.add("d-none")

        // Display general route information
        let totalDistance = 0
        let totalTime = 0
        for (const step of route.steps) {
            totalDistance += step.distance
            totalTime += step.time
        }
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
        const layers: L.Layer[] = []

        // Create a single geometry for the route
        const fullGeom: [number, number][] = []
        if (route.steps.length) {
            for (const step of route.steps) {
                fullGeom.push(...step.geom)
            }
            layers.push(L.polyline(fullGeom, styles.default))
        }

        let stepNumber = 0
        for (const step of route.steps) {
            stepNumber += 1
            const div = (stepTemplate.content.cloneNode(true) as DocumentFragment).children[0]
            div.querySelector(".icon div").classList.add(`icon-${step.code}`)
            div.querySelector(".number").textContent = `${stepNumber}.`
            div.querySelector(".instruction").textContent = step.text
            div.querySelector(".distance").textContent = formatDistanceRounded(step.distance)
            fragment.appendChild(div)

            const layer = L.polyline(step.geom, styles.hover)
            layers.push(layer)

            /** On mouseover, scroll result into view and focus the route segment */
            const onMouseover = () => {
                const sidebarRect = parentSidebar.getBoundingClientRect()
                const resultRect = div.getBoundingClientRect()
                const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
                if (!isVisible) div.scrollIntoView({ behavior: "smooth", block: "center" })

                div.classList.add("hover")
                layer.setStyle(styles.hoverActive)
            }

            /** On mouseout, unfocus the route segment */
            const onMouseout = () => {
                div.classList.remove("hover")
                layer.setStyle(styles.hover)
            }

            /** On click, show the popup */
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

    /** On routing error, display an error message */
    const onRoutingError = (error: Error): void => {
        loadingContainer.classList.add("d-none")
        routingErrorAlert.querySelector("p").textContent = error.message
        routingErrorAlert.classList.remove("d-none")
    }

    return {
        load: () => {
            // Listen for events
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            mapContainer.addEventListener("dragover", onMapDragOver)
            mapContainer.addEventListener("drop", onMapDrop)

            // Create the routing layer if it doesn't exist
            if (!map.hasLayer(routingLayer)) {
                if (!paneCreated) {
                    console.debug("Creating routing pane")
                    map.createPane("routing")
                    paneCreated = true
                }

                console.debug("Adding overlay layer", routingLayerId)
                map.addLayer(routingLayer)
                map.fire("overlayadd", { layer: routingLayer, name: routingLayerId })
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
            const routingEngine = getInitialRoutingEngine(searchParams.engine)
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
                console.debug("Removing overlay layer", routingLayerId)
                map.removeLayer(routingLayer)
                map.fire("overlayremove", { layer: routingLayer, name: routingLayerId })
            }

            // Clear the routing layer
            routingLayer.clearLayers()

            map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            mapContainer.removeEventListener("dragover", onMapDragOver)
            mapContainer.removeEventListener("drop", onMapDrop)

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

/** Get initial routing engine identifier */
const getInitialRoutingEngine = (engine?: string): string | null => {
    return engine ?? getLastRoutingEngine()
}
