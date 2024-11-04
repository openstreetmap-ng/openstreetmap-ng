import { fromBinary } from "@bufbuild/protobuf"
import { decode } from "@mapbox/polyline"
import i18next from "i18next"
import * as L from "leaflet"
import { formatDistance, formatDistanceRounded, formatHeight, formatTime } from "../_format-utils"
import { getLastRoutingEngine, setLastRoutingEngine } from "../_local-storage"
import { qsEncode, qsParse } from "../_qs"
import { configureStandardForm } from "../_standard-form"
import { getPageTitle } from "../_title"
import { zoomPrecision } from "../_utils"
import { type LayerId, getOverlayLayerById } from "../leaflet/_layers"
import { getMarkerIcon } from "../leaflet/_utils"
import { RoutingResolveNamesSchema, type RoutingRoute, RoutingRouteSchema } from "../proto/shared_pb"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

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
let paneCreated = false

/** Create a new routing controller */
export const getRoutingController = (map: L.Map): IndexController => {
    const mapContainer = map.getContainer()
    const routingLayer = getOverlayLayerById(routingLayerId) as L.FeatureGroup
    const sidebar = getActionSidebar("routing")
    const parentSidebar = sidebar.closest(".sidebar")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form.resolve-names-form")
    const startInput = form.elements.namedItem("start") as HTMLInputElement
    const startLoadedInput = form.elements.namedItem("start_loaded") as HTMLInputElement
    const startDraggableMarker = form.querySelector("img.draggable-marker[data-direction=start]")
    const endInput = form.elements.namedItem("end") as HTMLInputElement
    const endLoadedInput = form.elements.namedItem("end_loaded") as HTMLInputElement
    const endDraggableMarker = form.querySelector("img.draggable-marker[data-direction=end]")
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
    let startBounds: L.LatLngBounds | null = null
    let startMarker: L.Marker | null = null
    let endBounds: L.LatLngBounds | null = null
    let endMarker: L.Marker | null = null

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
    startDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)
    endDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)

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

        if (marker === startMarker) {
            startInput.value = value
            startInput.dispatchEvent(new Event("input"))
        } else if (marker === endMarker) {
            endInput.value = value
            endInput.dispatchEvent(new Event("input"))
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
        if (dragData === "start") {
            if (!startMarker) {
                startMarker = markerFactory("green")
                startMarker.addEventListener("dragend", onMapMarkerDragEnd)
                map.addLayer(startMarker)
            }
            marker = startMarker
        } else if (dragData === "end") {
            if (!endMarker) {
                endMarker = markerFactory("red")
                endMarker.addEventListener("dragend", onMapMarkerDragEnd)
                map.addLayer(endMarker)
            }
            marker = endMarker
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
        const newStartValue = endInput.value
        const newEndValue = startInput.value
        startInput.value = newStartValue
        startInput.dispatchEvent(new Event("input"))
        endInput.value = newEndValue
        endInput.dispatchEvent(new Event("input"))
        if (
            startMarker &&
            endMarker &&
            startInput.value === startLoadedInput.value &&
            endInput.value === endLoadedInput.value
        ) {
            const newStartLatLng = endMarker.getLatLng()
            const newEndLatLng = startMarker.getLatLng()
            startMarker.setLatLng(newStartLatLng)
            startLoadedInput.value = newStartValue
            endMarker.setLatLng(newEndLatLng)
            endLoadedInput.value = newEndValue
        }
        submitFormIfFilled()
    })

    /** Utility method to submit the form if filled with data */
    const submitFormIfFilled = () => {
        map.closePopup(popup)
        if (startInput.value && endInput.value) form.requestSubmit()
    }

    configureStandardForm(
        form,
        ({ protobuf }: { protobuf: Uint8Array }) => {
            // On success callback, call routing engine, display results, and update search params
            const data = fromBinary(RoutingResolveNamesSchema, protobuf)
            console.debug("onResolveNamesFormSuccess", data)

            if (data.start) {
                const entry = data.start
                const { minLon, minLat, maxLon, maxLat } = entry.bounds
                startBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
                startInput.value = entry.name
                startInput.dispatchEvent(new Event("input"))
                if (!startMarker) {
                    startMarker = markerFactory("green")
                    startMarker.addEventListener("dragend", onMapMarkerDragEnd)
                    map.addLayer(startMarker)
                }
                startMarker.setLatLng([entry.lat, entry.lon])
                startLoadedInput.value = entry.name
            }

            if (data.end) {
                const entry = data.end
                const { minLon, minLat, maxLon, maxLat } = entry.bounds
                endBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
                endInput.value = entry.name
                endInput.dispatchEvent(new Event("input"))
                if (!endMarker) {
                    endMarker = markerFactory("red")
                    endMarker.addEventListener("dragend", onMapMarkerDragEnd)
                    map.addLayer(endMarker)
                }
                endMarker.setLatLng([entry.lat, entry.lon])
                endLoadedInput.value = entry.name
            }

            // Focus on the makers if they're offscreen
            const markerBounds = startBounds.extend(endBounds)
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

        const precision = zoomPrecision(19)
        const startLatLng = startMarker.getLatLng()
        const endLatLng = endMarker.getLatLng()
        const startLon = startLatLng.lng.toFixed(precision)
        const startLat = startLatLng.lat.toFixed(precision)
        const endLon = endLatLng.lng.toFixed(precision)
        const endLat = endLatLng.lat.toFixed(precision)

        const startRouteParam = `${startLat},${startLon}`
        const endRouteParam = `${endLat},${endLon}`
        const routeParam = `${startRouteParam};${endRouteParam}`

        // Remember routing configuration in URL search params
        const url = new URL(location.href)
        url.searchParams.set("engine", routingEngineName)
        url.searchParams.set("route", routeParam)
        window.history.replaceState(null, "", url)

        loadingContainer.classList.remove("d-none")

        fetch(
            `/api/web/routing/route?${qsEncode({
                engine: routingEngineName,
                start_lon: startLon,
                start_lat: startLat,
                end_lon: endLon,
                end_lat: endLat,
            })}`,
            {
                method: "GET",
                mode: "same-origin",
                cache: "no-store",
                signal: abortController.signal,
                priority: "high",
            },
        )
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
                const buffer = await resp.arrayBuffer()
                const route = fromBinary(RoutingRouteSchema, new Uint8Array(buffer))
                onRoutingRouteSuccess(route)
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch routing route", error)
                onRoutingRouteError(error)
            })
            .finally(() => {
                loadingContainer.classList.add("d-none")
            })
    }

    /** On routing success, render the route */
    const onRoutingRouteSuccess = (route: RoutingRoute): void => {
        console.debug("onRoutingRouteSuccess", route)

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
        if (route.elevation) {
            routeElevationContainer.classList.remove("d-none")
            routeAscend.textContent = formatHeight(route.elevation.ascend)
            routeDescend.textContent = formatHeight(route.elevation.descend)
        } else {
            routeElevationContainer.classList.add("d-none")
        }

        // Render the turn-by-turn table
        const fragment = document.createDocumentFragment()
        const layers: L.Polyline[] = []

        // Create a single geometry for the route
        const stepsGeoms: [number, number][][] = []
        for (const step of route.steps) stepsGeoms.push(decode(step.line, 6))
        const fullGeom: [number, number][] = [].concat(...stepsGeoms)
        if (fullGeom.length) {
            layers.push(L.polyline(fullGeom, styles.default))
        }

        let stepNumber = 0
        for (const step of route.steps) {
            const stepGeom = stepsGeoms[stepNumber]
            stepNumber += 1

            const div = (stepTemplate.content.cloneNode(true) as DocumentFragment).children[0]
            div.querySelector(".icon div").classList.add(`icon-${step.iconNum}`)
            div.querySelector(".number").textContent = `${stepNumber}.`
            div.querySelector(".instruction").textContent = step.text
            div.querySelector(".distance").textContent = formatDistanceRounded(step.distance)
            fragment.appendChild(div)

            const layer = L.polyline(stepGeom, styles.hover)
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
                popup.setLatLng(stepGeom[0])
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
    const onRoutingRouteError = (error: Error): void => {
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
                const [start, end] = searchParams.route.split(";")
                startInput.value = start
                startInput.dispatchEvent(new Event("input"))
                endInput.value = end
                endInput.dispatchEvent(new Event("input"))
            }

            if (searchParams.from) {
                startInput.value = searchParams.from
                startInput.dispatchEvent(new Event("input"))
            }
            if (searchParams.to) {
                endInput.value = searchParams.to
                endInput.dispatchEvent(new Event("input"))
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

            if (startMarker) {
                map.removeLayer(startMarker)
                startMarker = null
                startLoadedInput.value = ""
            }
            if (endMarker) {
                map.removeLayer(endMarker)
                endMarker = null
                endLoadedInput.value = ""
            }

            map.closePopup(popup)
        },
    }
}

/** Get initial routing engine identifier */
const getInitialRoutingEngine = (engine?: string): string | null => {
    return engine ?? getLastRoutingEngine()
}
