import { decode, encode } from "@googlemaps/polyline-codec"
import * as L from "leaflet"
import { formatDistance } from "../_format-utils.js"
import { qsParse } from "../_qs.js"
import { range, throttle } from "../_utils.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"

const mapThrottleDelay = 16 // 60 FPS

const lineStyle = {
    color: "#6ea8fe",
    weight: 5,
    noClip: true,
}

const labelStyle = {
    keyboard: false,
    alt: "",
    zIndexOffset: -10,
    interactive: false,
}

const historyReplaceState = throttle((url) => window.history.replaceState(null, "", url), 250)

/**
 * Create a new distance measuring controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getDistanceController = (map) => {
    const mapContainer = map.getContainer()
    const sidebar = getActionSidebar("distance")
    const totalDistanceLabel = sidebar.querySelector(".total-distance")

    const positionsUrl = []
    const lines = []
    const labels = []
    const markers = []
    let dirtyMarkerIndices = []
    let ghostMarker = null
    let ghostMarkerIndex = null

    const markerFactory = (index, color) => {
        const onMarkerClick = () => {
            removeMarker(index)
        }
        const onMarkerDrag = throttle(() => update([index]), mapThrottleDelay)
        const marker = L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        })
        if (index >= 0) {
            // Listen for events on real markers
            marker.addEventListener("click", onMarkerClick)
            marker.addEventListener("drag", onMarkerDrag)
        }
        map.addLayer(marker)
        return marker
    }

    const ghostMarkerFactory = () => {
        const marker = markerFactory(-1, "blue")
        marker.setZIndexOffset(-10)
        marker.addEventListener("mousemove", onGhostMarkerMousemove)
        marker.addEventListener("mouseout", onGhostMarkerDragEnd)
        marker.addOneTimeEventListener("dragstart", onGhostMarkerDragStart)
        marker.addEventListener("drag", onGhostMarkerDrag)
        marker.addOneTimeEventListener("dragend", onGhostMarkerDragEnd)
        marker.addOneTimeEventListener("click", onGhostMarkerClick)

        const icon = marker._icon
        icon.classList.add("ghost-marker")
        return marker
    }

    const updateUrl = () => {
        const newLength = markers.length
        if (newLength < positionsUrl.length) {
            // Truncate positions
            positionsUrl.length = newLength
        }
        for (const markerIndex of dirtyMarkerIndices) {
            positionsUrl[markerIndex] = markers[markerIndex].getLatLng()
        }
        const url = new URL(location.href)
        url.searchParams.set("line", encode(positionsUrl, 5))
        historyReplaceState(url)
    }

    const updateLines = () => {
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

    const updateLabels = () => {
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

                const distance = startPoint.distanceTo(endPoint)
                const distanceText = formatDistance(distance)

                const label = labels[labelIndexOffset]
                label.setLatLng(middlePoint)
                label.distance = distance
                const container = label._icon.firstChild
                container.style.transform = `rotate(${angle}rad)`
                container.textContent = distanceText
            }
        }
        let totalDistance = 0
        for (const label of labels) totalDistance += label.distance
        totalDistanceLabel.textContent = formatDistance(totalDistance)
    }

    const update = (dirtyIndices) => {
        // dirtyIndices must be sorted
        dirtyMarkerIndices = dirtyIndices
        updateUrl()
        updateLines()
        updateLabels()
        dirtyMarkerIndices.length = 0
        map.fire("viewreset") // fix z-index
    }

    const removeMarker = (index) => {
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

    const insertMarker = (index, latLng) => {
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

    const onMapClick = (options) => {
        console.debug("onMapClick", options)
        const { latlng, skipUpdates } = options
        const markerIndex = markers.length
        // Turn previous marker into blue
        if (markerIndex >= 2) {
            markers[markerIndex - 1].setIcon(getMarkerIcon("blue", true))
        }
        // Create new marker
        const marker = markerFactory(markerIndex, markerIndex === 0 ? "green" : "red")
        marker.setLatLng(latlng)
        markers.push(marker)
        if (!skipUpdates) update([markerIndex])
    }

    const onLineMouseover = ({ latlng }) => {
        // find closest point on line
        const point = map.latLngToLayerPoint(latlng)
        let minDistance = Number.POSITIVE_INFINITY
        let minLatLng = null
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

    const onGhostMarkerMousemove = ({ originalEvent }) => {
        // Convert browser event to map event
        const rect = mapContainer.getBoundingClientRect()
        const x = originalEvent.clientX - rect.left
        const y = originalEvent.clientY - rect.top
        onLineMouseover({ latlng: map.containerPointToLatLng([x, y]) })
    }

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

    const onGhostMarkerDrag = (e) => {
        const marker = markers[ghostMarkerIndex]
        marker.setLatLng(ghostMarker.getLatLng())
        marker.fire(e.type, e)
    }

    const onGhostMarkerDragEnd = () => {
        console.debug("onGhostMarkerDragEnd", ghostMarker !== null)
        // Remove ghost marker
        ghostMarker?.remove()
        ghostMarker = null
    }

    const onGhostMarkerClick = () => {
        console.debug("onGhostMarkerClick")
        onGhostMarkerDragStart()
        onGhostMarkerDragEnd()
    }

    return {
        load: () => {
            // Listen for events
            map.addEventListener("click", onMapClick)

            switchActionSidebar(map, "distance")

            // Load markers from URL
            const searchParams = qsParse(location.search.substring(1))
            let positions = []
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
            onGhostMarkerDragEnd()
            for (const marker of markers) marker.remove()
            markers.length = 0
            update([])
            map.removeEventListener("click", onMapClick)
        },
    }
}
