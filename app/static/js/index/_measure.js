import { qsEncode, qsParse } from "../_qs.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"
import * as L from "leaflet"

const logTen = Math.log(10)

export const getMeasuringController = (map) => {
    const sidebar = getActionSidebar("measure")
    const totalDistanceLabel = sidebar.querySelector(".total-distance")
    const markers = []
    let divIcons = []
    let line = null
    let distance = 0
    let headMarker = null

    const formatDistance = (distance) => {
        // TODO: support for miles
        const precision = 10 ** (2 - Math.floor(Math.log(distance) / logTen)) || 1
        const roundedMeters = Math.round(distance * precision) / precision || 1
        const num = roundedMeters < 1000 ? `${roundedMeters}m` : `${roundedMeters / 1000}km`
        return num
    }

    const updateLabel = (index) => {
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

        const icon = L.marker(middle, {
            icon: L.divIcon({
                className: "measure-label",
                html: `<div style="transform:rotate(${angle}deg)">${num}</div>`,
                iconSize: [0, 0],
            }),
        }).addTo(map)
        divIcons.push(icon)
        distance += _distance
        totalDistanceLabel.innerText = formatDistance(distance)
    }

    const updateLabels = () => {
        distance = 0
        for (const icon of divIcons) {
            icon.remove()
        }
        divIcons = []
        for (let index = 1; index < markers.length; index++) {
            updateLabel(index)
        }
    }

    const updateLine = () => {
        const latLngs = markers.map((marker) => marker.getLatLng())

        line.setLatLngs(latLngs)
        updateLabels()
    }

    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        })
            .addTo(map)
            .on("drag", updateLine)

    const mouseClick = (e) => {
        const pos = e.containerPoint
        const markerPos = map.latLngToContainerPoint(markers[markers.length - 1].getLatLng())
        const diff = { x: pos.x - markerPos.x, y: pos.y - markerPos.y }
        const distance = diff.x * diff.x + diff.y * diff.y
        if (distance < 1000) return // skip creating marker if it is close to the previous one

        // skip first marker
        if (markers.length > 1) {
            const marker = markerFactory("blue")
                .setLatLng(markers[markers.length - 1].getLatLng())
                .addEventListener("click", () => {
                    markers.splice(markers.indexOf(marker), 1)
                    marker.remove()
                    updateLine()
                })
            markers.splice(markers.length - 1, 0, marker)
        } else {
            headMarker = markerFactory("red")
            markers.push(headMarker)
            headMarker.addEventListener("click", () => {
                if (markers.length === 2) return
                const lastMarker = markers[markers.length - 2]
                markers.splice(markers.length - 2, 1)
                headMarker.setLatLng(lastMarker.getLatLng())
                lastMarker.remove()
                updateLine()
            })
        }
        headMarker.setLatLng(e.latlng)
        line.addLatLng(e.latlng)
        updateLabel(markers.length - 1)
    }

    const onLineClick = (e) => {
        // skip adding marker
        map.removeEventListener("click", mouseClick)
        setTimeout(() => map.addEventListener("click", mouseClick), 0)
    }

    return {
        load: () => {
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.pos) {
                const [lat, lon] = searchParams.pos.split(",")
                const startMarker = markerFactory("green").setLatLng([lat, lon])
                markers.push(startMarker)
                startMarker.addEventListener("click", () => {
                    if (!markers[2]) return
                    startMarker.setLatLng(markers[1].getLatLng())
                    markers[1].remove()
                    markers.splice(1, 1)
                    updateLine()
                })

                line = L.polyline([[lat, lon]], { color: "yellow", weight: 5 }).addTo(map)
                totalDistanceLabel.innerText = "0km"
                switchActionSidebar(map, "measure")
            }

            map.addEventListener("click", mouseClick)
            line.addEventListener("click", onLineClick)
        },
        unload: () => {
            // activeElements.forEach((marker, index) => {
            //     marker.remove()
            //     delete activeElements[index]
            // })
            map.removeEventListener("click", mouseClick)
            line.removeEventListener("click", onLineClick)
        },
    }
}
