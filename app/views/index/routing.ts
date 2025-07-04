import { fromBinary } from "@bufbuild/protobuf"
import type { Feature, LineString } from "geojson"
import i18next from "i18next"
import {
    type GeoJSONSource,
    type LngLat,
    LngLatBounds,
    type LngLatLike,
    type Map as MaplibreMap,
    Marker,
    Point,
    Popup,
} from "maplibre-gl"
import {
    formatDistance,
    formatDistanceRounded,
    formatHeight,
    formatTime,
} from "../lib/format-utils"
import { routingEngineStorage } from "../lib/local-storage"
import { clearMapHover, setMapHover } from "../lib/map/hover"
import {
    addMapLayer,
    emptyFeatureCollection,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "../lib/map/layers/layers"
import { getMarkerIconElement, markerIconAnchor } from "../lib/map/utils"
import { decodeLonLat } from "../lib/polyline"
import { type RoutingResult, RoutingResultSchema } from "../lib/proto/shared_pb"
import { qsParse } from "../lib/qs"
import { configureStandardForm } from "../lib/standard-form"
import { setPageTitle } from "../lib/title"
import { zoomPrecision } from "../lib/utils"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

const layerId = "routing" as LayerId
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["line"],
    layerOptions: {
        layout: {
            "line-join": "round",
            "line-cap": "round",
        },
        paint: {
            "line-color": ["case", ["boolean", ["get", "base"], false], "#03f", "#ff0"],
            "line-opacity": [
                "case",
                ["boolean", ["get", "base"], false],
                0.3, // Complete route is always 0.3 opacity
                ["boolean", ["feature-state", "hover"], false],
                0.5, // Individual steps are 0.5 when hovered
                0, // Individual steps are invisible when not hovered
            ],
            "line-width": 10,
        },
    },
    priority: 110,
})

const dragDataType = "text/osm-routing-direction"

/** Create a new routing controller */
export const getRoutingController = (map: MaplibreMap): IndexController => {
    const source = map.getSource(layerId) as GeoJSONSource
    const mapContainer = map.getContainer()
    const sidebar = getActionSidebar("routing")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const form = sidebar.querySelector("form.routing-form")
    const startInput = form.elements.namedItem("start") as HTMLInputElement
    const startLoadedInput = form.elements.namedItem("start_loaded") as HTMLInputElement
    const startLoadedLonInput = form.elements.namedItem(
        "start_loaded_lon",
    ) as HTMLInputElement
    const startLoadedLatInput = form.elements.namedItem(
        "start_loaded_lat",
    ) as HTMLInputElement
    const startDraggableMarker = form.querySelector(
        "img.draggable-marker[data-direction=start]",
    )
    const endInput = form.elements.namedItem("end") as HTMLInputElement
    const endLoadedInput = form.elements.namedItem("end_loaded") as HTMLInputElement
    const endLoadedLonInput = form.elements.namedItem(
        "end_loaded_lon",
    ) as HTMLInputElement
    const endLoadedLatInput = form.elements.namedItem(
        "end_loaded_lat",
    ) as HTMLInputElement
    const endDraggableMarker = form.querySelector(
        "img.draggable-marker[data-direction=end]",
    )
    const reverseButton = form.querySelector("button.reverse-btn")
    const engineInput = form.elements.namedItem("engine") as HTMLInputElement
    const bboxInput = form.elements.namedItem("bbox") as HTMLInputElement
    const loadingContainer = sidebar.querySelector(".loading")
    const routeContainer = sidebar.querySelector(".route")
    const routeDistance = routeContainer.querySelector(".route-info .distance")
    const routeTime = routeContainer.querySelector(".route-info .time")
    const routeElevationContainer = routeContainer.querySelector(
        ".route-elevation-info",
    )
    const routeAscend = routeElevationContainer.querySelector(".ascend")
    const routeDescend = routeElevationContainer.querySelector(".descend")
    const stepsTableBody = routeContainer.querySelector(".route-steps tbody")
    const attribution = routeContainer.querySelector(".attribution")
    const popupTemplate = routeContainer.querySelector("template.popup")
    const stepTemplate = routeContainer.querySelector("template.step")

    let startBounds: LngLatBounds | null = null
    let startMarker: Marker | null = null
    let endBounds: LngLatBounds | null = null
    let endMarker: Marker | null = null

    const popup = new Popup({
        closeButton: false,
        closeOnMove: true,
        anchor: "bottom",
        className: "route-steps",
    })

    const markerFactory = (color: string): Marker =>
        new Marker({
            anchor: markerIconAnchor,
            element: getMarkerIconElement(color, true),
            draggable: true,
        })

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

    const openPopup = (result: Element, lngLat: LngLatLike): void => {
        const content = popupTemplate.content.cloneNode(true) as DocumentFragment
        content.querySelector(".number").innerHTML =
            result.querySelector(".number").innerHTML
        content.querySelector(".instruction").innerHTML =
            result.querySelector(".instruction").innerHTML
        popup.setDOMContent(content).setLngLat(lngLat).addTo(map)
    }

    // On feature click, open a popup
    map.on("click", layerId, (e) => {
        const feature = e.features[0] as Feature<LineString>
        const featureId = feature.id as number
        const result = stepsTableBody.children[featureId]
        openPopup(result, feature.geometry.coordinates[0] as LngLatLike)
    })

    let hoveredFeatureId: number | null = null
    map.on("mousemove", layerId, (e) => {
        const featureId = e.features[0].id
        if (hoveredFeatureId !== null) {
            if (hoveredFeatureId === featureId) return
            setHover(hoveredFeatureId, false)
        } else {
            setMapHover(map, layerId)
        }
        hoveredFeatureId = featureId as number
        setHover(hoveredFeatureId, true)
    })
    map.on("mouseleave", layerId, () => {
        setHover(hoveredFeatureId, false)
        hoveredFeatureId = null
        clearMapHover(map, layerId)
    })

    /** Set the hover state of the step features */
    const setHover = (id: number, hover: boolean): void => {
        const result = stepsTableBody.children[id]
        result?.classList.toggle("hover", hover)

        if (hover && result) {
            // Scroll result into view
            const sidebarRect = sidebar.getBoundingClientRect()
            const resultRect = result.getBoundingClientRect()
            const isVisible =
                resultRect.top >= sidebarRect.top &&
                resultRect.bottom <= sidebarRect.bottom
            if (!isVisible)
                result.scrollIntoView({ behavior: "smooth", block: "center" })
        }

        map.setFeatureState({ source: layerId, id: id }, { hover })
    }

    /** On marker drag end, update the form's coordinates */
    const onMapMarkerDragEnd = (lngLat: LngLat, isStart: boolean): void => {
        console.debug("onMapMarkerDragEnd", lngLat, isStart)

        const precision = zoomPrecision(map.getZoom())
        const lon = lngLat.lng.toFixed(precision)
        const lat = lngLat.lat.toFixed(precision)
        const value = `${lat}, ${lon}`

        if (isStart) {
            startInput.value = value
            startInput.dispatchEvent(new Event("input"))
        } else {
            endInput.value = value
            endInput.dispatchEvent(new Event("input"))
        }

        submitFormIfFilled()
    }

    /** On map drag over, prevent default behavior */
    const onMapDragOver = (event: DragEvent) => event.preventDefault()

    /** On map marker drop, update the marker's coordinates */
    const onMapDrop = (event: DragEvent) => {
        const dragData = event.dataTransfer.getData(dragDataType)
        console.debug("onMapDrop", dragData)

        let marker: Marker
        if (dragData === "start") {
            if (!startMarker) {
                startMarker = markerFactory("green")
                startMarker.on("dragend", () =>
                    onMapMarkerDragEnd(startMarker.getLngLat(), true),
                )
            }
            marker = startMarker
        } else if (dragData === "end") {
            if (!endMarker) {
                endMarker = markerFactory("red")
                endMarker.on("dragend", () =>
                    onMapMarkerDragEnd(endMarker.getLngLat(), false),
                )
            }
            marker = endMarker
        } else {
            return
        }

        const mapRect = mapContainer.getBoundingClientRect()
        const mousePoint = new Point(
            event.clientX - mapRect.left,
            event.clientY - mapRect.top,
        )
        marker.setLngLat(map.unproject(mousePoint)).addTo(map).fire("dragend")
    }

    /** On map update, update the form's bounding box */
    const onMapZoomOrMoveEnd = () => {
        const [[minLon, minLat], [maxLon, maxLat]] = map
            .getBounds()
            .adjustAntiMeridian()
            .toArray()
        bboxInput.value = `${minLon},${minLat},${maxLon},${maxLat}`
    }

    // On engine input change, remember the last routing engine
    engineInput.addEventListener("input", () => {
        console.debug("onEngineInputChange")
        routingEngineStorage.set(engineInput.value)
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
            const newStartLngLat = endMarker.getLngLat()
            const newEndLngLat = startMarker.getLngLat()
            startMarker.setLngLat(newStartLngLat)
            startLoadedInput.value = newStartValue
            endMarker.setLngLat(newEndLngLat)
            endLoadedInput.value = newEndValue
        }
        submitFormIfFilled()
    })

    /** Utility method to submit the form if filled with data */
    const submitFormIfFilled = () => {
        popup.remove()
        if (startInput.value && endInput.value) form.requestSubmit()
    }

    configureStandardForm(
        form,
        ({ protobuf }: { protobuf: Uint8Array }) => {
            // Return early if unloaded
            if (loadingContainer.classList.contains("d-none")) return
            loadingContainer.classList.add("d-none")

            // On success callback, call routing engine, display results, and update search params
            const data = fromBinary(RoutingResultSchema, protobuf)
            console.debug("onRoutingFormSuccess", data)

            updateEndpoints(data)
            updateUrl()
            updateRoute(data)
        },
        () => {
            // On client validation, hide previous route data
            loadingContainer.classList.remove("d-none")
            routeContainer.classList.add("d-none")
            return null
        },
        () => {
            // Return early if unloaded
            if (loadingContainer.classList.contains("d-none")) return
            loadingContainer.classList.add("d-none")
        },
        { abortSignal: true },
    )

    const updateEndpoints = (data: RoutingResult): void => {
        if (data.start) {
            const entry = data.start
            const { minLon, minLat, maxLon, maxLat } = entry.bounds
            startBounds = new LngLatBounds([minLon, minLat, maxLon, maxLat])
            startInput.value = entry.name
            startInput.dispatchEvent(new Event("input"))
            if (!startMarker) {
                startMarker = markerFactory("green")
                startMarker.on("dragend", () =>
                    onMapMarkerDragEnd(startMarker.getLngLat(), true),
                )
            }
            startMarker.setLngLat([entry.lon, entry.lat]).addTo(map)
            startLoadedInput.value = entry.name
            startLoadedLonInput.value = entry.lon.toFixed(7)
            startLoadedLatInput.value = entry.lat.toFixed(7)
        }

        if (data.end) {
            const entry = data.end
            const { minLon, minLat, maxLon, maxLat } = entry.bounds
            endBounds = new LngLatBounds([minLon, minLat, maxLon, maxLat])
            endInput.value = entry.name
            endInput.dispatchEvent(new Event("input"))
            if (!endMarker) {
                endMarker = markerFactory("red")
                endMarker.on("dragend", () =>
                    onMapMarkerDragEnd(endMarker.getLngLat(), false),
                )
            }
            endMarker.setLngLat([entry.lon, entry.lat]).addTo(map)
            endLoadedInput.value = entry.name
            endLoadedLonInput.value = entry.lon.toFixed(7)
            endLoadedLatInput.value = entry.lat.toFixed(7)
        }

        // Focus on the makers if they're offscreen
        const mapBounds = map.getBounds()
        const markerBounds = startBounds.extend(endBounds)
        if (
            !mapBounds.contains(markerBounds.getSouthWest()) &&
            !mapBounds.contains(markerBounds.getNorthEast())
        ) {
            map.fitBounds(markerBounds)
        }
    }

    const updateUrl = (): void => {
        const routingEngineName = engineInput.value

        const precision = zoomPrecision(19)
        const startLngLat = startMarker.getLngLat()
        const endLngLat = endMarker.getLngLat()
        const startLon = startLngLat.lng.toFixed(precision)
        const startLat = startLngLat.lat.toFixed(precision)
        const endLon = endLngLat.lng.toFixed(precision)
        const endLat = endLngLat.lat.toFixed(precision)

        const startRouteParam = `${startLat},${startLon}`
        const endRouteParam = `${endLat},${endLon}`
        const routeParam = `${startRouteParam};${endRouteParam}`

        // Remember routing configuration in URL search params
        const url = new URL(window.location.href)
        url.searchParams.set("engine", routingEngineName)
        url.searchParams.set("route", routeParam)
        window.history.replaceState(null, "", url)
    }

    const updateRoute = (route: RoutingResult): void => {
        const lines: Feature<LineString>[] = []
        const allCoords = decodeLonLat(route.line, route.lineQuality)

        // Add the complete route geometry
        if (allCoords.length) {
            lines.push({
                type: "Feature",
                id: -1,
                properties: { base: true },
                geometry: {
                    type: "LineString",
                    coordinates: allCoords,
                },
            })
        }

        // Process individual steps
        let totalDistance = 0
        let totalTime = 0
        let coordsSliceStart = 0
        const stepsRows = document.createDocumentFragment()
        for (const [stepIndex, step] of route.steps.entries()) {
            totalDistance += step.distance
            totalTime += step.time

            const stepCoords = allCoords.slice(
                coordsSliceStart,
                coordsSliceStart + step.numCoords,
            )
            coordsSliceStart += step.numCoords - 1 // adjusted for overlapping ends
            if (step.numCoords > 1) {
                lines.push({
                    type: "Feature",
                    id: stepIndex,
                    properties: {},
                    geometry: {
                        type: "LineString",
                        coordinates: stepCoords,
                    },
                })
            }

            const div = (stepTemplate.content.cloneNode(true) as DocumentFragment)
                .children[0]
            div.querySelector(".icon div").classList.add(
                `icon-${step.iconNum}`,
                "dark-filter-invert",
            )
            div.querySelector(".number").textContent = `${stepIndex + 1}.`
            div.querySelector(".instruction").textContent = step.text
            div.querySelector(".distance").textContent = formatDistanceRounded(
                step.distance,
            )
            div.addEventListener("click", () => openPopup(div, stepCoords[0]))
            div.addEventListener("mouseenter", () => setHover(stepIndex, true))
            div.addEventListener("mouseleave", () => setHover(stepIndex, false))
            stepsRows.append(div)
        }

        // Display general route information
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

        // Display the turn-by-turn table
        stepsTableBody.innerHTML = ""
        stepsTableBody.append(stepsRows)
        attribution.innerHTML = i18next.t(
            "javascripts.directions.instructions.courtesy",
            {
                link: route.attribution,
                interpolation: { escapeValue: false },
            },
        )
        routeContainer.classList.remove("d-none")

        // Update the route layer
        source.setData({ type: "FeatureCollection", features: lines })
        console.debug("Route showing", route.steps.length, "steps")
    }

    return {
        load: () => {
            switchActionSidebar(map, sidebar)
            setPageTitle(sidebarTitle)

            // Initial update to set the inputs
            onMapZoomOrMoveEnd()

            // Allow default form setting via URL search parameters
            const searchParams = qsParse(window.location.search)
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
                    // Don't trigger event to avoid repeated submitFormIfFilled():
                    // engineInput.dispatchEvent(new Event("input"))
                } else {
                    console.warn("Unsupported routing engine", routingEngine)
                }
            }

            submitFormIfFilled()
            addMapLayer(map, layerId)
            // Listen for events
            map.on("moveend", onMapZoomOrMoveEnd)
            mapContainer.addEventListener("dragover", onMapDragOver)
            mapContainer.addEventListener("drop", onMapDrop)
        },
        unload: () => {
            map.off("moveend", onMapZoomOrMoveEnd)
            removeMapLayer(map, layerId)
            source.setData(emptyFeatureCollection)
            clearMapHover(map, layerId)
            mapContainer.removeEventListener("dragover", onMapDragOver)
            mapContainer.removeEventListener("drop", onMapDrop)

            loadingContainer.classList.add("d-none")
            routeContainer.classList.add("d-none")

            startMarker?.remove()
            startMarker = null
            startLoadedInput.value = ""

            endMarker?.remove()
            endMarker = null
            endLoadedInput.value = ""

            popup.remove()
        },
    }
}

/** Get initial routing engine identifier */
const getInitialRoutingEngine = (engine?: string): string | null => {
    return engine ?? routingEngineStorage.get()
}
