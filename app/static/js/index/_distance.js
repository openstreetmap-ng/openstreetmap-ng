import { qsEncode, qsParse } from "../_qs.js"
import { formatDistance } from "../_format-utils.js"

import { getMarkerIcon } from "../leaflet/_utils.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"
import * as L from "leaflet"

const logTen = Math.log(10)

export const getMeasuringController = (map) => {
    const sidebar = getActionSidebar("distance")
    const totalDistanceLabel = sidebar.querySelector(".total-distance")
    let markers = []
    let divIcons = []
    let line = null
    let distance = 0
    let param = ""
    let ghostMarker = null
    let ghostMarkerIndex = null
    let supress = false

    map.createPane("labelPane")
    map.getPane("labelPane").style.zIndex = 400
    map.getPane("labelPane").style.pointerEvents = "none"

    const saveParam = () => {
        if (param[0] === ";") param = param.substring(1)
        const url = new URL(document.URL)
        url.searchParams.set("pos", param)
        history.replaceState(null, "", url)
    }

    const addLabel = (index) => {
        const point = markers[index].getLatLng()
        const previous = markers[index - 1].getLatLng()
        const middle = L.LineUtil.polylineCenter([point, previous], L.CRS.EPSG3857)
        const screenPoint = map.latLngToContainerPoint(point)
        const previousScreen = map.latLngToContainerPoint(previous)
        const _distance = point.distanceTo(previous)
        const num = formatDistance(_distance)
        let angle =
            (-Math.atan2(screenPoint.x - previousScreen.x, screenPoint.y - previousScreen.y) * 180) / Math.PI + 90

        if (angle > 90) angle -= 180
        if (angle < -90) angle += 180

        const label = L.marker(middle, {
            pane: "labelPane",
            icon: L.divIcon({
                className: "distance-label",
                html: `<div style="transform:rotate(${angle}deg)">${num}</div>`,
                iconSize: [0, 0],
            }),
        })
            .addTo(map)
            .addEventListener("mousemove", onLineHover)
        divIcons.push(label)
        param += `;${point.lat.toFixed(4)},${point.lng.toFixed(4)}`

        distance += _distance
        totalDistanceLabel.innerText = formatDistance(distance)
    }

    const addLabels = () => {
        distance = 0
        const point = markers[0].getLatLng()
        param = `${point.lat.toFixed(4)},${point.lng.toFixed(4)}`
        for (const icon of divIcons) {
            icon.remove()
        }
        divIcons = []
        for (let index = 1; index < markers.length; index++) {
            addLabel(index)
        }
    }

    const reAdd = () => {
        updateLine()
        addLabels()
    }

    const updateLine = () => {
        const latLngs = markers.map((marker) => marker.getLatLng())
        line.setLatLngs(latLngs)
    }

    const onMarkerDrag = () => {
        // after dragging markers have wrong z-indexes
        map.fire("viewreset")

        reAdd()
    }

    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        })
            .addTo(map)
            .on("drag", onMarkerDrag)
            .on("dragend", saveParam)

    const onHeadMarkerClick = () => {
        if (markers.length === 2) return
        const lastMarker = markers[markers.length - 2] // remove second to last marker from array
        markers.splice(markers.length - 2, 1)
        markers[markers.length - 1].setLatLng(lastMarker.getLatLng())
        lastMarker.remove() // remove second to last marker from map
        reAdd()
        saveParam()
    }

    const onTailMarkerClick = () => {
        if (!markers[2]) return
        markers[0].setLatLng(markers[1].getLatLng())
        markers[1].remove()
        markers.splice(1, 1)
        reAdd()
        saveParam()
    }

    const addMarker = (e) => {
        if (supress) return
        // if there are 0 markers create green one
        if (markers.length === 0) {
            const startMarker = markerFactory("green").setLatLng(e.latlng)
            markers.push(startMarker)
            startMarker.addEventListener("click", onTailMarkerClick)
            param = `${e.latlng.lat.toFixed(4)},${e.latlng.lng.toFixed(4)}`
            line = L.polyline([e.latlng], { color: "#6ea8fe", weight: 5, noClip: true }).addTo(map)
            line.addEventListener("mousemove", onLineHover)
            totalDistanceLabel.innerText = "0km"
            return
        }

        // if there is 1 marker create red marker, else blue
        if (markers.length === 1) {
            const headMarker = markerFactory("red")
            markers.push(headMarker)
            headMarker.addEventListener("click", onHeadMarkerClick)
        } else {
            const marker = markerFactory("blue")
                .setLatLng(markers[markers.length - 1].getLatLng())
                .addEventListener("click", () => {
                    removeMarker(marker)
                })
            markers.splice(markers.length - 1, 0, marker)
        }

        markers[markers.length - 1].setLatLng(e.latlng)
        line.addLatLng(e.latlng)
        addLabel(markers.length - 1)
        saveParam()
    }

    const removeMarker = (marker) => {
        markers.splice(markers.indexOf(marker), 1)
        marker.remove()
        reAdd()
        saveParam()
    }

    const createGhostMarker = () => {
        let dragged = false

        // clear unused event listiners after ghost marker has became normal marker
        const clear = () => {
            removeEventListener("click", click)
            removeEventListener("click", selfRemove)
            removeEventListener("dragstart", selfRemove)
            removeEventListener("mousemove", mousemove)
        }

        const mousemove = (e) => {
            if (dragged) return
            const rect = map._container.getBoundingClientRect()
            const x = e.originalEvent.clientX - rect.left
            const y = e.originalEvent.clientY - rect.top
            onLineHover({ latlng: map.containerPointToLatLng([x, y]) })
        }

        const selfRemove = () => {
            if (dragged) return
            if (marker !== ghostMarker) return

            // make ghost marker a real marker
            markers = [...markers.slice(0, ghostMarkerIndex), ghostMarker, ...markers.slice(ghostMarkerIndex)]
            ghostMarker._icon.style.opacity = "100%"
            ghostMarker = null

            // skip adding normal marker
            supress = true
            const listener = () => {
                setTimeout(() => {
                    supress = false
                    removeEventListener("mouseup", listener)
                }, 0)
            }
            map.addEventListener("mouseup", listener)

            reAdd()
            saveParam()
            dragged = true
            clear()
        }

        const click = () => {
            if (!dragged) return
            ghostMarker = null
            removeMarker(marker)
            clear()
        }
        const marker = markerFactory("blue")
            .addEventListener("click", click)
            .addEventListener("dragstart click", selfRemove)
            .addEventListener("mousemove", mousemove)
        marker._icon.style.opacity = "50%"
        marker._icon.style.paddingBottom = "10px"
        marker._icon.style.zIndex = "0"
        marker._icon.style.boxSizing = "content-box"
        return marker
    }

    const onLineHover = (e) => {
        // skip adding marker
        map.removeEventListener("click", addMarker)
        setTimeout(() => map.addEventListener("click", addMarker), 0)

        // find closest point on line
        let minPoint = null
        let minDistance = Number.POSITIVE_INFINITY
        ghostMarkerIndex = 0

        for (let i = 1; i < markers.length; i++) {
            const marker = markers[i]
            const previous = markers[i - 1]
            const point = L.LineUtil.closestPointOnSegment(
                map.latLngToLayerPoint(e.latlng),
                map.latLngToLayerPoint(marker.getLatLng()),
                map.latLngToLayerPoint(previous.getLatLng()),
            )
            const distance = map.distance(map.layerPointToLatLng(point), e.latlng)
            if (distance < minDistance) {
                minPoint = point
                minDistance = distance
                ghostMarkerIndex = i
            }
        }
        if (!ghostMarker) {
            const marker = createGhostMarker()
            ghostMarker = marker
        }
        ghostMarker.setLatLng(map.layerPointToLatLng(minPoint))
    }

    const checkHover = (e) => {
        if (e.target === ghostMarker?._icon || e.target === line?._path || e.target in divIcons.map((e) => e._icon))
            return
        ghostMarker?.remove()
        ghostMarker = null
    }

    return {
        load: () => {
            distance = 0
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.pos) {
                const positions = searchParams.pos.split(";")
                if (positions.length === 0) return
                for (const pos of positions) {
                    const [lat, lng] = pos.split(",").map(Number)

                    // Grecefully handle errors
                    if (Number.isNaN(lat + lng) && !Number.isFinite(lat + lng)) continue

                    addMarker({ latlng: { lat: lat, lng: lng } })
                }
            }

            if (markers.length > 1) {
                const bounds = line.getBounds()
                map.fitBounds(bounds, {
                    animate: false,
                })
            }

            switchActionSidebar(map, "distance")
            map.addEventListener("click", addMarker)
            document.addEventListener("mousemove", checkHover)
        },
        unload: () => {
            for (const label of divIcons) {
                label?.remove()
            }
            for (const label of markers) {
                label?.remove()
            }
            divIcons = []
            markers = []
            line?.remove()
            ghostMarker?.remove()
            line = null
            ghostMarker = null

            map.removeEventListener("click", addMarker)
            line?.removeEventListener("mousemove", onLineHover)
        },
    }
}
