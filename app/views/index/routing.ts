import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import { tryParsePoint, zoomPrecision } from "@lib/coords"
import {
    formatDistance,
    formatDistanceRounded,
    formatHeight,
    formatTime,
} from "@lib/format"
import { routingEngineStorage } from "@lib/local-storage"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import {
    addMapLayer,
    emptyFeatureCollection,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "@lib/map/layers/layers"
import {
    getMarkerIconElement,
    MARKER_ICON_ANCHOR,
    type MarkerColor,
} from "@lib/map/marker"
import { decodeLonLat } from "@lib/polyline"
import {
    type RoutingResult,
    type RoutingResult_Endpoint,
    RoutingResultSchema,
} from "@lib/proto/shared_pb"
import { qsParse } from "@lib/qs"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import type { Feature, LineString } from "geojson"
import i18next from "i18next"
import {
    type GeoJSONSource,
    LngLatBounds,
    type LngLatLike,
    type Map as MaplibreMap,
    Marker,
    Point,
    Popup,
} from "maplibre-gl"

const LAYER_ID = "routing" as LayerId
layersConfig.set(LAYER_ID, {
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

const DRAG_DATA_TYPE = "text/osm-routing-direction"
const DRAG_IMAGE_WIDTH = 25
const DRAG_IMAGE_HEIGHT = 41
const DRAG_IMAGE_OFFSET_X = 12
const DRAG_IMAGE_OFFSET_Y = 21

export const getRoutingController = (map: MaplibreMap) => {
    const source = map.getSource<GeoJSONSource>(LAYER_ID)!
    const mapContainer = map.getContainer()
    const sidebar = getActionSidebar("routing")
    const parentSidebar = sidebar.closest("div.sidebar")!
    const sidebarTitle = sidebar.querySelector(".sidebar-title")!.textContent
    const form = sidebar.querySelector("form.routing-form")!
    const startInput = form.querySelector("input[name=start]")!
    const startLoadedInput = form.querySelector("input[name=start_loaded]")!
    const startLoadedLonInput = form.querySelector("input[name=start_loaded_lon]")!
    const startLoadedLatInput = form.querySelector("input[name=start_loaded_lat]")!
    const startDraggableMarker = form.querySelector(
        "img.draggable-marker[data-direction=start]",
    )!
    const endInput = form.querySelector("input[name=end]")!
    const endLoadedInput = form.querySelector("input[name=end_loaded]")!
    const endLoadedLonInput = form.querySelector("input[name=end_loaded_lon]")!
    const endLoadedLatInput = form.querySelector("input[name=end_loaded_lat]")!
    const endDraggableMarker = form.querySelector(
        "img.draggable-marker[data-direction=end]",
    )!
    const reverseButton = form.querySelector("button.reverse-btn")!
    const engineInput = form.querySelector("select[name=engine]")!
    const bboxInput = form.querySelector("input[name=bbox]")!
    const loadingContainer = sidebar.querySelector(".loading")!
    const routeContainer = sidebar.querySelector(".route")!
    const routeDistance = routeContainer.querySelector(".route-info .distance")!
    const routeTime = routeContainer.querySelector(".route-info .time")!
    const routeElevationContainer = routeContainer.querySelector(
        ".route-elevation-info",
    )!
    const routeAscend = routeElevationContainer.querySelector(".ascend")!
    const routeDescend = routeElevationContainer.querySelector(".descend")!
    const stepsTableBody = routeContainer.querySelector(".route-steps tbody")!
    const attribution = routeContainer.querySelector(".attribution")!
    const popupTemplate = routeContainer.querySelector("template.popup")!
    const stepTemplate = routeContainer.querySelector("template.step")!

    let startBounds: LngLatBounds | undefined
    let startMarker: Marker | null = null
    let endBounds: LngLatBounds | undefined
    let endMarker: Marker | null = null
    let hoverId: number | null = null
    let lastMouse: [number, number] | undefined

    const popup = new Popup({
        closeButton: false,
        closeOnMove: true,
        anchor: "bottom",
        className: "route-steps",
    })

    const markerFactory = (color: MarkerColor) =>
        new Marker({
            anchor: MARKER_ICON_ANCHOR,
            element: getMarkerIconElement(color, true),
            draggable: true,
        })

    const getOrCreateMarker = (dir: "start" | "end") => {
        if (dir === "start") {
            if (!startMarker) {
                startMarker = markerFactory("green")
                startMarker.on("dragend", () => onMapMarkerDragEnd(startMarker, true))
            }
            return startMarker
        }

        if (!endMarker) {
            endMarker = markerFactory("red")
            endMarker.on("dragend", () => onMapMarkerDragEnd(endMarker, false))
        }
        return endMarker
    }

    const onInterfaceMarkerDragStart = (e: DragEvent) => {
        const target = e.target as HTMLImageElement
        const direction = target.dataset.direction!
        console.debug("onInterfaceMarkerDragStart", direction)

        const dt = e.dataTransfer!
        dt.effectAllowed = "move"
        dt.setData("text/plain", "")
        dt.setData(DRAG_DATA_TYPE, direction)
        const canvas = document.createElement("canvas")
        canvas.width = DRAG_IMAGE_WIDTH
        canvas.height = DRAG_IMAGE_HEIGHT
        const ctx = canvas.getContext("2d")!
        ctx.drawImage(target, 0, 0, DRAG_IMAGE_WIDTH, DRAG_IMAGE_HEIGHT)
        dt.setDragImage(canvas, DRAG_IMAGE_OFFSET_X, DRAG_IMAGE_OFFSET_Y)
    }
    startDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)
    endDraggableMarker.addEventListener("dragstart", onInterfaceMarkerDragStart)

    const openPopup = (result: Element, lngLat: LngLatLike) => {
        const content = popupTemplate.content.cloneNode(true) as DocumentFragment
        content.querySelector(".number")!.innerHTML =
            result.querySelector(".number")!.innerHTML
        content.querySelector(".instruction")!.innerHTML =
            result.querySelector(".instruction")!.innerHTML
        popup.setDOMContent(content).setLngLat(lngLat).addTo(map)
    }

    // Show step instruction details on click
    map.on("click", LAYER_ID, (e) => {
        const feature = e.features![0] as Feature<LineString>
        const featureId = feature.id as number
        const result = stepsTableBody.children[featureId]
        openPopup(result, feature.geometry.coordinates[0] as LngLatLike)
    })

    // Sync hover between map features and sidebar table
    map.on("mousemove", LAYER_ID, (e) => {
        const id = e.features![0].id as number
        setMapHover(map, LAYER_ID)
        updateHover(id >= 0 ? id : null, true)
    })
    map.on("mouseleave", LAYER_ID, () => {
        clearMapHover(map, LAYER_ID)
        updateHover(null)
    })

    const updateHover = (id: number | null, scrollIntoView = false) => {
        if (id === hoverId) return

        if (hoverId !== null) {
            const prev = stepsTableBody.children[hoverId]
            prev?.classList.remove("hover")
            map.setFeatureState({ source: LAYER_ID, id: hoverId }, { hover: false })
        }

        hoverId = id

        if (id !== null) {
            const result = stepsTableBody.children[id]
            result?.classList.add("hover")

            if (scrollIntoView && result) {
                const sidebarRect = parentSidebar.getBoundingClientRect()
                const resultRect = result.getBoundingClientRect()
                const isVisible =
                    resultRect.top >= sidebarRect.top &&
                    resultRect.bottom <= sidebarRect.bottom
                if (!isVisible)
                    result.scrollIntoView({ behavior: "smooth", block: "center" })
            }
            map.setFeatureState({ source: LAYER_ID, id }, { hover: true })
        }
    }

    const onSidebarMouseMove = (e: MouseEvent) => {
        lastMouse = [e.clientX, e.clientY]
    }

    const onSidebarScroll = () => {
        if (!lastMouse) return
        const [x, y] = lastMouse
        const r = parentSidebar.getBoundingClientRect()
        if (x < r.left || x > r.right || y < r.top || y > r.bottom) return
        const row = document.elementFromPoint(x, y)?.closest("tr[data-step-index]")
        updateHover(row ? Number.parseInt(row.dataset.stepIndex!, 10) : null)
    }

    const onMapMarkerDragEnd = (marker: Marker | null, isStart: boolean) => {
        if (!marker) return
        const lngLat = marker.getLngLat()
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

    const onMapDragOver = (e: DragEvent) => e.preventDefault()

    const onMapDrop = (e: DragEvent) => {
        const dragData = e.dataTransfer!.getData(DRAG_DATA_TYPE)
        console.debug("onMapDrop", dragData)

        let marker: Marker
        if (dragData === "start") marker = getOrCreateMarker("start")
        else if (dragData === "end") marker = getOrCreateMarker("end")
        else return

        const mapRect = mapContainer.getBoundingClientRect()
        const mousePoint = new Point(e.clientX - mapRect.left, e.clientY - mapRect.top)
        marker.setLngLat(map.unproject(mousePoint)).addTo(map).fire("dragend")
    }

    const ensureMarkerFromInput = (dir: "start" | "end") => {
        const input = dir === "start" ? startInput : endInput
        const coords = tryParsePoint(input.value)
        if (!coords) return
        const [lon, lat] = coords

        const marker = getOrCreateMarker(dir)
        marker.setLngLat([lon, lat]).addTo(map)

        if (dir === "start") {
            startLoadedInput.value = input.value
            startLoadedLonInput.value = lon.toFixed(7)
            startLoadedLatInput.value = lat.toFixed(7)
        } else {
            endLoadedInput.value = input.value
            endLoadedLonInput.value = lon.toFixed(7)
            endLoadedLatInput.value = lat.toFixed(7)
        }
    }

    const onMapZoomOrMoveEnd = () => {
        const [[minLon, minLat], [maxLon, maxLat]] = map
            .getBounds()
            .adjustAntiMeridian()
            .toArray()
        bboxInput.value = `${minLon},${minLat},${maxLon},${maxLat}`
    }

    // Persist engine selection to avoid re-selecting on future visits
    engineInput.addEventListener("input", () => {
        console.debug("onEngineInputChange")
        routingEngineStorage.set(engineInput.value)
        submitFormIfFilled()
    })

    // Swap route direction and update markers
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

    const submitFormIfFilled = () => {
        popup.remove()
        if (startInput.value && endInput.value) form.requestSubmit()
    }

    configureStandardForm(
        form,
        (data) => {
            // Return early if unloaded
            if (loadingContainer.classList.contains("d-none")) return
            loadingContainer.classList.add("d-none")

            // Update UI with server-computed route
            console.debug("onRoutingFormSuccess", data)
            updateEndpoints(data)
            updateUrl()
            updateRoute(data)
        },
        {
            abortSignal: true,
            protobuf: RoutingResultSchema,
            validationCallback: () => {
                // Hide previous route data before submission
                loadingContainer.classList.remove("d-none")
                routeContainer.classList.add("d-none")
                return null
            },
            errorCallback: () => {
                // Return early if unloaded
                if (loadingContainer.classList.contains("d-none")) return
                loadingContainer.classList.add("d-none")
            },
        },
    )

    const updateEndpoints = (data: RoutingResult) => {
        const updateEndpoint = (
            dir: "start" | "end",
            entry: RoutingResult_Endpoint,
        ) => {
            const { minLon, minLat, maxLon, maxLat } = entry.bounds!
            const b = new LngLatBounds([minLon, minLat, maxLon, maxLat])
            if (dir === "start") startBounds = b
            else endBounds = b

            const input = dir === "start" ? startInput : endInput
            input.value = entry.name
            input.dispatchEvent(new Event("input"))
            getOrCreateMarker(dir).setLngLat([entry.lon, entry.lat]).addTo(map)

            if (dir === "start") {
                startLoadedInput.value = entry.name
                startLoadedLonInput.value = entry.lon.toFixed(7)
                startLoadedLatInput.value = entry.lat.toFixed(7)
            } else {
                endLoadedInput.value = entry.name
                endLoadedLonInput.value = entry.lon.toFixed(7)
                endLoadedLatInput.value = entry.lat.toFixed(7)
            }
        }

        if (data.start) updateEndpoint("start", data.start)
        if (data.end) updateEndpoint("end", data.end)

        const markerBounds =
            startBounds && endBounds
                ? startBounds.extend(endBounds)
                : (startBounds ?? endBounds)
        if (markerBounds) {
            const mapBounds = map.getBounds()
            if (
                !(
                    mapBounds.contains(markerBounds.getSouthWest()) ||
                    mapBounds.contains(markerBounds.getNorthEast())
                )
            )
                map.fitBounds(markerBounds)
        }
    }

    const updateUrl = () => {
        if (!(startMarker && endMarker)) return
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

    const updateRoute = (route: RoutingResult) => {
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

            const div = stepTemplate.content.firstElementChild!.cloneNode(
                true,
            ) as HTMLElement
            div.dataset.stepIndex = String(stepIndex)
            div.querySelector(".icon div")!.classList.add(
                `icon-${step.iconNum}`,
                "dark-filter-invert",
            )
            div.querySelector(".number")!.textContent = `${stepIndex + 1}.`
            div.querySelector(".instruction")!.textContent = step.text
            div.querySelector(".distance")!.textContent = formatDistanceRounded(
                step.distance,
            )
            div.addEventListener("click", () => openPopup(div, stepCoords[0]))
            div.addEventListener("mouseenter", () => updateHover(stepIndex))
            div.addEventListener("mouseleave", () => updateHover(null))
            stepsRows.append(div)
        }

        // Display general route information
        routeDistance.textContent = formatDistance(totalDistance)
        routeTime.textContent = formatTime(totalTime)

        // Display the optional elevation information
        routeElevationContainer.classList.toggle("d-none", !route.elevation)
        if (route.elevation) {
            routeAscend.textContent = formatHeight(route.elevation.ascend)
            routeDescend.textContent = formatHeight(route.elevation.descend)
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

            // Ensure markers reflect any prefilled inputs (persisted or from params)
            ensureMarkerFromInput("start")
            ensureMarkerFromInput("end")

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
            addMapLayer(map, LAYER_ID)
            // Keep bbox in sync with map viewport
            map.on("moveend", onMapZoomOrMoveEnd)
            mapContainer.addEventListener("dragover", onMapDragOver)
            mapContainer.addEventListener("drop", onMapDrop)
            parentSidebar.addEventListener("mousemove", onSidebarMouseMove)
            parentSidebar.addEventListener("scroll", onSidebarScroll)
        },
        unload: () => {
            map.off("moveend", onMapZoomOrMoveEnd)
            removeMapLayer(map, LAYER_ID)
            source.setData(emptyFeatureCollection)
            clearMapHover(map, LAYER_ID)
            mapContainer.removeEventListener("dragover", onMapDragOver)
            mapContainer.removeEventListener("drop", onMapDrop)
            parentSidebar.removeEventListener("mousemove", onSidebarMouseMove)
            parentSidebar.removeEventListener("scroll", onSidebarScroll)

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

const getInitialRoutingEngine = (engine?: string) => {
    return engine ?? routingEngineStorage.get()
}
