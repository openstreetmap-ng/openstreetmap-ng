import { decode, encode } from "@mapbox/polyline"
import type { Feature, LineString } from "geojson"
import {
    type GeoJSONSource,
    type LngLat,
    LngLatBounds,
    type LngLatLike,
    type Map as MaplibreMap,
    Marker,
} from "maplibre-gl"
import { formatDistance } from "../_format-utils"
import { qsParse } from "../_qs"
import { range, throttle } from "../_utils"
import { type LayerId, addMapLayer, emptyFeatureCollection, layersConfig, removeMapLayer } from "../leaflet/_layers"
import { closestPointOnSegment, getMarkerIconElement, markerIconAnchor } from "../leaflet/_utils"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

const mapThrottleDelay = 16 // 60 FPS

const layerId = "distance" as LayerId
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
            "line-color": "#6ea8fe",
            "line-width": 5,
        },
    },
    priority: 160,
})

/** Like window.history.replaceState, but throttled */
const throttledHistoryReplaceState = throttle(
    (url: string | URL | null): void => window.history.replaceState(null, "", url),
    250,
)

/** Create a new distance measuring controller */
export const getDistanceController = (map: MaplibreMap): IndexController => {
    const source = map.getSource(layerId) as GeoJSONSource
    const sidebar = getActionSidebar("distance")
    const totalDistanceLabel = sidebar.querySelector(".total-distance")

    const positionsUrl: [number, number][] = []
    const lines: Feature<LineString>[] = []
    const labels: Marker[] = []
    const markers: Marker[] = []
    let dirtyMarkerIndices: number[] = []
    let ghostMarker: Marker | null = null
    let ghostMarkerIndex = -1

    const markerFactory = (index: number, color: string): Marker => {
        const marker = new Marker({
            anchor: markerIconAnchor,
            element: getMarkerIconElement(color, true),
            draggable: true,
        }).addTo(map)
        // Listen for events on real markers
        if (index >= 0) {
            // On marker drag, update the state
            marker.on(
                "drag",
                throttle(() => update([index]), mapThrottleDelay),
            )
            // On marker click, remove that marker
            marker.once("click", () => removeMarker(index))
        }
        return marker
    }

    const ghostMarkerFactory = (): Marker => {
        const marker = markerFactory(-1, "blue")
        marker.addClassName("ghost-marker")
        marker.on("mousemove", updateGhostMarker)
        marker.on("mouseleave", onGhostMarkerDragEnd)
        marker.once("dragstart", onGhostMarkerDragStart)
        marker.on("drag", onGhostMarkerDrag)
        marker.once("dragend", onGhostMarkerDragEnd)
        marker.once("click", onGhostMarkerClick)
        return marker
    }

    /** Update the URL with the current line data */
    const updateUrl = (): void => {
        const newLength = markers.length
        if (newLength < positionsUrl.length) {
            // Truncate positions
            positionsUrl.length = newLength
        }
        for (const markerIndex of dirtyMarkerIndices) {
            const lngLat = markers[markerIndex].getLngLat()
            positionsUrl[markerIndex] = [lngLat.lat, lngLat.lng]
        }
        const url = new URL(window.location.href)
        url.searchParams.set("line", encode(positionsUrl, 5))
        throttledHistoryReplaceState(url)
    }

    const updateLines = (): void => {
        const newLength = Math.max(markers.length - 1, 0)
        if (newLength < lines.length) {
            // Truncate lines
            lines.length = newLength
        }
        for (const markerIndex of dirtyMarkerIndices) {
            const lineIndex = markerIndex - 1
            if (lineIndex >= lines.length) {
                // Create new line
                lines[lineIndex] = {
                    type: "Feature",
                    id: lineIndex,
                    properties: {},
                    geometry: {
                        type: "LineString",
                        coordinates: [
                            markers[markerIndex - 1].getLngLat().toArray(),
                            markers[markerIndex].getLngLat().toArray(),
                        ],
                    },
                }
            }
            for (const lineIndexOffset of [lineIndex, lineIndex + 1]) {
                // Update existing line (before and after)
                if (lineIndexOffset < 0 || lineIndexOffset >= lines.length) continue
                lines[lineIndexOffset].geometry.coordinates = [
                    markers[lineIndexOffset].getLngLat().toArray(),
                    markers[lineIndexOffset + 1].getLngLat().toArray(),
                ]
            }
        }
        source.setData({
            type: "FeatureCollection",
            features: lines,
        })
    }

    const updateLabels = (): void => {
        const newLength = Math.max(markers.length - 1, 0)
        if (newLength < labels.length) {
            // Truncate labels
            for (let i = newLength; i < labels.length; i++) labels[i].remove()
            labels.length = newLength
        }
        for (const markerIndex of dirtyMarkerIndices) {
            const labelIndex = markerIndex - 1
            if (labelIndex >= labels.length) {
                // Create new label
                const label = new Marker({
                    anchor: "center",
                    element: document.createElement("div"),
                    className: "distance-label",
                }).addTo(map)
                label.on("mouseenter", updateGhostMarker)
                labels[labelIndex] = label
            }
            for (const labelIndexOffset of [labelIndex, labelIndex + 1]) {
                // Update existing label (before and after)
                if (labelIndexOffset < 0 || labelIndexOffset >= labels.length) continue

                const startPoint = markers[labelIndexOffset].getLngLat()
                const endPoint = markers[labelIndexOffset + 1].getLngLat()
                const middlePoint: LngLatLike = [
                    (startPoint.lng + endPoint.lng) / 2,
                    (startPoint.lat + endPoint.lat) / 2,
                ]
                const startScreenPoint = map.project(startPoint)
                const endScreenPoint = map.project(endPoint)

                let angle = Math.atan2(endScreenPoint.y - startScreenPoint.y, endScreenPoint.x - startScreenPoint.x)
                if (angle > Math.PI / 2) angle -= Math.PI
                if (angle < -Math.PI / 2) angle += Math.PI

                const label = labels[labelIndexOffset]
                label.setLngLat(middlePoint)
                const distance = startPoint.distanceTo(endPoint)
                ;(label as any).distance = distance
                label.setRotation((angle * 180) / Math.PI)
                label.getElement().textContent = formatDistance(distance)
            }
        }
        let totalDistance = 0
        for (const label of labels) totalDistance += (label as any).distance
        totalDistanceLabel.textContent = formatDistance(totalDistance)
    }

    /** Quickly update the modified state, dirtyIndices must be sorted */
    const update = (dirtyIndices: number[]): void => {
        dirtyMarkerIndices = dirtyIndices
        updateUrl()
        updateLines()
        updateLabels()
        dirtyMarkerIndices.length = 0
    }

    /** Remove a marker from the map */
    const removeMarker = (index: number): void => {
        console.debug("removeMarker", index)
        // Pop tailing markers
        const tail = markers.splice(index + 1)
        {
            // Remove indexed marker
            const marker = markers[index]
            marker.remove()
            markers.length = index
        }
        update([])

        if (tail.length) {
            // Add markers back
            for (const marker of tail) {
                const lngLat = marker.getLngLat()
                marker.remove()
                onMapClick({ lngLat, skipUpdates: true })
            }
            update(range(index, markers.length))
        } else if (index >= 2) {
            // If no tail, turn previous marker into red
            markers[index - 1].getElement().replaceWith(getMarkerIconElement("red", true))
        }
    }

    const insertMarker = (index: number, lngLat: LngLatLike) => {
        console.debug("insertMarker", index, lngLat)
        // Pop tailing markers
        const tail = markers.splice(index)
        update([])

        // Add new marker
        onMapClick({ lngLat, skipUpdates: true })

        // Add markers back
        for (const marker of tail) {
            const markerLngLat = marker.getLngLat()
            marker.remove()
            onMapClick({ lngLat: markerLngLat, skipUpdates: true })
        }
        update(range(index, markers.length))
    }

    /** On map click, create a new marker */
    const onMapClick = (options: { lngLat: LngLatLike; skipUpdates?: boolean }): void => {
        console.debug("onMapClick", options)
        const markerIndex = markers.length
        // Turn previous marker into blue
        if (markerIndex >= 2) {
            markers[markerIndex - 1].getElement().replaceWith(getMarkerIconElement("blue", true))
        }
        // Create new marker
        const marker = markerFactory(markerIndex, markerIndex === 0 ? "green" : "red")
        marker.setLngLat(options.lngLat)
        markers.push(marker)
        if (!options.skipUpdates) update([markerIndex])
    }

    /** On lise mouseover, show the ghost marker */
    const updateGhostMarker = ({ lngLat }: { lngLat: LngLat }): void => {
        const point = map.project(lngLat)
        let minDistance = Number.POSITIVE_INFINITY
        let minLngLat: LngLat | null = null
        ghostMarkerIndex = -1
        for (let i = 1; i < markers.length; i++) {
            const closestLngLat = map.unproject(
                closestPointOnSegment(
                    point,
                    map.project(markers[i - 1].getLngLat()),
                    map.project(markers[i].getLngLat()),
                ),
            )
            const distance = closestLngLat.distanceTo(lngLat)
            if (distance < minDistance) {
                minDistance = distance
                minLngLat = closestLngLat
                ghostMarkerIndex = i
            }
        }
        if (!ghostMarker) ghostMarker = ghostMarkerFactory()
        ghostMarker.setLngLat(minLngLat)
    }
    map.on("mouseenter", layerId, updateGhostMarker)

    /** On ghost marker drag start, replace it with a real marker */
    const onGhostMarkerDragStart = () => {
        console.debug("onGhostMarkerDragStart")
        // Hide ghost marker
        ghostMarker.addClassName("dragging") // TODO: zindex + opacity
        ghostMarker.off("mousemove", updateGhostMarker)
        ghostMarker.off("mouseleave", onGhostMarkerDragEnd)
        ghostMarker.off("click", onGhostMarkerClick)
        // Add a real marker
        insertMarker(ghostMarkerIndex, ghostMarker.getLngLat())
    }

    /** On ghost marker drag, update the real marker position */
    const onGhostMarkerDrag = (e: Event) => {
        const marker = markers[ghostMarkerIndex]
        marker.setLngLat(ghostMarker.getLngLat())
        marker.fire(e.type, e)
    }

    /** On ghost marker drag end, remove the ghost marker, leaving the real marker in its place */
    const onGhostMarkerDragEnd = () => {
        console.debug("onGhostMarkerDragEnd", ghostMarker !== null)
        // Remove ghost marker
        ghostMarker?.remove()
        ghostMarker = null
    }

    /** On ghost marker click, convert it into a real marker */
    const onGhostMarkerClick = () => {
        console.debug("onGhostMarkerClick")
        onGhostMarkerDragStart()
        onGhostMarkerDragEnd()
    }

    return {
        load: () => {
            switchActionSidebar(map, sidebar)

            // Load markers from URL
            const searchParams = qsParse(location.search.substring(1))
            let positions: [number, number][] = []
            if (searchParams.line) {
                try {
                    positions = decode(searchParams.line, 5)
                } catch (error) {
                    console.error("Failed to decode line points from", searchParams.line, error)
                }
            }
            for (const [lat, lon] of positions) {
                onMapClick({ lngLat: [lon, lat], skipUpdates: true })
            }
            console.debug("Loaded", positions.length, "line points")
            update(range(0, markers.length))

            // Focus on the makers if they're offscreen
            if (markers.length > 1) {
                const mapBounds = map.getBounds()
                let markerBounds = new LngLatBounds(markers[0].getLngLat())
                let contains = true
                for (const marker of markers.slice(1)) {
                    const markerLngLat = marker.getLngLat()
                    markerBounds = markerBounds.extend(markerLngLat)
                    if (contains && !mapBounds.contains(markerLngLat)) contains = false
                }
                if (!contains) map.fitBounds(markerBounds, { animate: false })
            }

            addMapLayer(map, layerId)
            map.on("click", onMapClick)
        },
        unload: () => {
            map.off("click", onMapClick)
            removeMapLayer(map, layerId)
            source.setData(emptyFeatureCollection)
            onGhostMarkerDragEnd()
            for (const marker of markers) marker.remove()
            markers.length = 0
            update([])
        },
    }
}
