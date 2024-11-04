import { decode, encode } from "@mapbox/polyline"
import * as L from "leaflet"
import { formatDistance } from "../_format-utils"
import { qsParse } from "../_qs"
import { range, throttle } from "../_utils"
import { getMarkerIcon } from "../leaflet/_utils"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

const mapThrottleDelay = 16 // 60 FPS

const lineStyle: L.PolylineOptions = {
    color: "#6ea8fe",
    weight: 5,
    noClip: true,
}

const labelStyle: L.MarkerOptions = {
    keyboard: false,
    alt: "",
    zIndexOffset: -10,
    interactive: false,
}

/** Like window.history.replaceState, but throttled */
const throttledHistoryReplaceState = throttle(
    (url: string | URL | null): void => window.history.replaceState(null, "", url),
    250,
)

/** Create a new distance measuring controller */
export const getDistanceController = (map: L.Map): IndexController => {
    const mapContainer = map.getContainer()
    const sidebar = getActionSidebar("distance")
    const totalDistanceLabel = sidebar.querySelector(".total-distance")

    const positionsUrl: [number, number][] = []
    const lines: L.Polyline[] = []
    const labels: L.Marker[] = []
    const markers: L.Marker[] = []
    let dirtyMarkerIndices: number[] = []
    let ghostMarker: L.Marker | null = null
    let ghostMarkerIndex = -1

    const markerFactory = (index: number, color: string): L.Marker => {
        const marker = L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        })
        // Listen for events on real markers
        if (index >= 0) {
            // On marker click, remove that marker
            marker.addEventListener("click", () => {
                removeMarker(index)
            })
            // On marker drag, update the state
            marker.addEventListener("drag", () => {
                throttle(() => update([index]), mapThrottleDelay)
            })
        }
        map.addLayer(marker)
        return marker
    }

    const ghostMarkerFactory = (): L.Marker => {
        const marker = markerFactory(-1, "blue")
        marker.setZIndexOffset(-10)
        marker.addEventListener("mousemove", onGhostMarkerMousemove)
        marker.addEventListener("mouseout", onGhostMarkerDragEnd)
        marker.addOneTimeEventListener("dragstart", onGhostMarkerDragStart)
        marker.addEventListener("drag", onGhostMarkerDrag)
        marker.addOneTimeEventListener("dragend", onGhostMarkerDragEnd)
        marker.addOneTimeEventListener("click", onGhostMarkerClick)

        // @ts-ignore
        const icon: Element = marker._icon
        icon.classList.add("ghost-marker")
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
            const latlng = markers[markerIndex].getLatLng()
            positionsUrl[markerIndex] = [latlng.lat, latlng.lng]
        }
        const url = new URL(window.location.href)
        url.searchParams.set("line", encode(positionsUrl, 5))
        throttledHistoryReplaceState(url)
    }

    const updateLines = (): void => {
        const newLength = Math.max(markers.length - 1, 0)
        if (newLength < lines.length) {
            // Truncate lines
            for (const line of lines.splice(newLength)) line.remove()
        }
        for (const markerIndex of dirtyMarkerIndices) {
            const lineIndex = markerIndex - 1
            if (lineIndex >= lines.length) {
                // Create new line
                const line = L.polyline(
                    [markers[markerIndex - 1].getLatLng(), markers[markerIndex].getLatLng()],
                    lineStyle,
                )
                line.addEventListener("mouseover", onLineMouseover)
                lines[lineIndex] = line
                map.addLayer(line)
            }
            for (const offset of [0, 1]) {
                // Update existing line (before and after)
                const lineIndexOffset = lineIndex + offset
                if (lineIndexOffset < 0 || lineIndexOffset >= lines.length) continue
                lines[lineIndexOffset].setLatLngs([
                    markers[lineIndexOffset].getLatLng(),
                    markers[lineIndexOffset + 1].getLatLng(),
                ])
            }
        }
    }

    const updateLabels = (): void => {
        const newLength = Math.max(markers.length - 1, 0)
        if (newLength < labels.length) {
            // Truncate labels
            for (const label of labels.splice(newLength)) label.remove()
        }
        for (const markerIndex of dirtyMarkerIndices) {
            const labelIndex = markerIndex - 1
            if (labelIndex >= labels.length) {
                // Create new label
                const label = L.marker(L.latLng(0, 0), {
                    ...labelStyle,
                    icon: L.divIcon({
                        className: "distance-label",
                        html: "<div></div>",
                    }),
                })
                label.addEventListener("mouseover", onLineMouseover)
                labels[labelIndex] = label
                map.addLayer(label)
            }
            for (const offset of [0, 1]) {
                // Update existing label (before and after)
                const labelIndexOffset = labelIndex + offset
                if (labelIndexOffset < 0 || labelIndexOffset >= labels.length) continue

                const startPoint = markers[labelIndexOffset].getLatLng()
                const endPoint = markers[labelIndexOffset + 1].getLatLng()
                const middlePoint = L.LineUtil.polylineCenter([startPoint, endPoint], L.CRS.EPSG3857)
                const startScreenPoint = map.latLngToContainerPoint(startPoint)
                const endScreenPoint = map.latLngToContainerPoint(endPoint)

                let angle = Math.atan2(endScreenPoint.y - startScreenPoint.y, endScreenPoint.x - startScreenPoint.x)
                if (angle > Math.PI / 2) angle -= Math.PI
                if (angle < -Math.PI / 2) angle += Math.PI

                const label = labels[labelIndexOffset]
                label.setLatLng(middlePoint)
                const distance = startPoint.distanceTo(endPoint)
                ;(label as any).distance = distance
                // @ts-ignore
                const container: HTMLElement = label._icon.firstChild
                container.style.transform = `rotate(${angle}rad)`
                container.textContent = formatDistance(distance)
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
        map.fire("viewreset") // fix z-index
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
                const latLng = marker.getLatLng()
                marker.remove()
                onMapClick({ latlng: latLng, skipUpdates: true })
            }
            update(range(index, markers.length))
        } else if (index >= 2) {
            // If no tail, turn previous marker into red
            markers[index - 1].setIcon(getMarkerIcon("red", true))
        }
    }

    const insertMarker = (index: number, latLng: any) => {
        console.debug("insertMarker", index, latLng)
        // Pop tailing markers
        const tail = markers.splice(index)
        update([])

        // Add new marker
        onMapClick({ latlng: latLng, skipUpdates: true })

        // Add markers back
        for (const marker of tail) {
            const latLng = marker.getLatLng()
            marker.remove()
            onMapClick({ latlng: latLng, skipUpdates: true })
        }
        update(range(index, markers.length))
    }

    /** On map click, create a new marker */
    const onMapClick = (options: { latlng: L.LatLngExpression; skipUpdates?: boolean }): void => {
        console.debug("onMapClick", options)
        const markerIndex = markers.length
        // Turn previous marker into blue
        if (markerIndex >= 2) {
            markers[markerIndex - 1].setIcon(getMarkerIcon("blue", true))
        }
        // Create new marker
        const marker = markerFactory(markerIndex, markerIndex === 0 ? "green" : "red")
        marker.setLatLng(options.latlng)
        markers.push(marker)
        if (!options.skipUpdates) update([markerIndex])
    }

    /** On lise mouseover, show the ghost marker */
    const onLineMouseover = ({ latlng }: { latlng: L.LatLngExpression }): void => {
        // Find closest point on line
        const point = map.latLngToLayerPoint(latlng)
        let minDistance = Number.POSITIVE_INFINITY
        let minLatLng: L.LatLng | null = null
        ghostMarkerIndex = -1
        for (let i = 1; i < markers.length; i++) {
            const closestLatLng = map.layerPointToLatLng(
                L.LineUtil.closestPointOnSegment(
                    point,
                    map.latLngToLayerPoint(markers[i - 1].getLatLng()),
                    map.latLngToLayerPoint(markers[i].getLatLng()),
                ),
            )
            const distance = closestLatLng.distanceTo(latlng)
            if (distance < minDistance) {
                minDistance = distance
                minLatLng = closestLatLng
                ghostMarkerIndex = i
            }
        }
        if (!ghostMarker) ghostMarker = ghostMarkerFactory()
        ghostMarker.setLatLng(minLatLng)
    }

    /** On ghost marker mousemove, update the ghost marker position */
    const onGhostMarkerMousemove = ({ originalEvent }: L.LeafletMouseEvent) => {
        // Convert browser event to map event
        const rect = mapContainer.getBoundingClientRect()
        const x = originalEvent.clientX - rect.left
        const y = originalEvent.clientY - rect.top
        onLineMouseover({ latlng: map.containerPointToLatLng([x, y]) })
    }

    /** On ghost marker drag start, replace it with a real marker */
    const onGhostMarkerDragStart = () => {
        console.debug("onGhostMarkerDragStart")
        ghostMarker.removeEventListener("mousemove", onGhostMarkerMousemove)
        ghostMarker.removeEventListener("mouseout", onGhostMarkerDragEnd)
        ghostMarker.removeEventListener("click", onGhostMarkerClick)
        // Hide ghost marker
        ghostMarker.setZIndexOffset(10)
        ghostMarker.setOpacity(0)
        // Add a real marker
        insertMarker(ghostMarkerIndex, ghostMarker.getLatLng())
    }

    /** On ghost marker drag, update the real marker position */
    const onGhostMarkerDrag = (e: L.LeafletEvent) => {
        const marker = markers[ghostMarkerIndex]
        marker.setLatLng(ghostMarker.getLatLng())
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
            switchActionSidebar(map, "distance")

            map.addEventListener("click", onMapClick)

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
                onMapClick({ latlng: { lat, lng: lon }, skipUpdates: true })
            }
            console.debug("Loaded", positions.length, "line points")
            update(range(0, markers.length))

            // Focus on the makers if they're offscreen
            if (markers.length > 1) {
                const latLngs = markers.map((marker) => marker.getLatLng())
                const markerBounds = L.latLngBounds(latLngs)
                if (!map.getBounds().contains(markerBounds)) {
                    map.fitBounds(markerBounds, { animate: false })
                }
            }
        },
        unload: () => {
            map.removeEventListener("click", onMapClick)
            onGhostMarkerDragEnd()
            for (const marker of markers) marker.remove()
            markers.length = 0
            update([])
        },
    }
}
