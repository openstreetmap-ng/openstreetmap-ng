import { qsEncode, qsParse } from "../_qs.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import * as L from "leaflet"

const logTen = Math.log(10)

export const getMeasuringController = (map) => {
    const markers = []
    var divIcons = []
    var line = null
    var currentMarker = null

    const updateLabel = (index) => {
        const point = markers[index]?.getLatLng() || currentMarker.getLatLng()
        const previous = markers[index - 1].getLatLng()
        const middle = { lat: (point.lat + previous.lat) / 2, lon: (point.lng + previous.lng) / 2 }
        const distance = point.distanceTo(previous)
        const precision = Math.pow(10, 2 - Math.floor(Math.log(distance) / logTen)) || 1
        const roundedMeters = Math.round(distance * precision) / precision
        const num = roundedMeters < 1000 ? `${roundedMeters}m` : `${roundedMeters / 1000}km`
        var angle = (-Math.atan2(point.lat - previous.lat, point.lng - previous.lng) * 180) / Math.PI
        console.log(angle)
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
    }

    const updateLables = () => {
        var len = markers.length - 1
        if (currentMarker.getLatLng().lat != 100) len++
        divIcons.forEach((icon) => icon.remove())
        divIcons = []
        for (let index = 0; index < len; index++) {
            updateLabel(index + 1)
        }
    }

    const updateLine = () => {
        const latLngs = markers.map((marker) => marker.getLatLng())
        // skip first marker
        if (currentMarker.getLatLng().lat != 100) {
            latLngs.push(currentMarker.getLatLng())
        }

        line.setLatLngs(latLngs)
        updateLables()
    }

    const markerFactory = (color) =>
        L.marker(L.latLng(100, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        })
            .addTo(map)
            .on("drag", updateLine)

    const mouseClick = (e) => {
        // skip first marker
        if (currentMarker.getLatLng().lat != 100) {
            const marker = markerFactory("blue")
                .setLatLng(currentMarker.getLatLng())
                .addEventListener("click", () => {
                    markers.splice(markers.indexOf(marker), 1)
                    marker.remove()
                    updateLine()
                })
            markers.push(marker)
        }
        currentMarker.setLatLng(e.latlng)
        line.addLatLng(e.latlng)
        updateLabel(markers.length)
    }

    const onLineClick = (e) => {
        // skip adding marker
        map.removeEventListener("click", mouseClick)
        setTimeout(() => map.addEventListener("click", mouseClick), 0)
        console.log(line.closestLayerPoint(e.latlng))
    }

    return {
        load: () => {
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.pos) {
                const [lat, lon] = searchParams.pos.split(",")
                const startMarker = markerFactory("green").setLatLng([lat, lon])
                markers.push(startMarker)
                startMarker.addEventListener("click", () => {
                    if (!markers[1]) return
                    startMarker.setLatLng(markers[1].getLatLng())
                    markers[1].remove()
                    markers.splice(1, 1)
                    updateLine()
                })
                currentMarker = markerFactory("red")
                currentMarker.addEventListener("click", () => {
                    if (markers.length == 1) return
                    const lastMarker = markers.pop()
                    currentMarker.setLatLng(lastMarker.getLatLng())
                    lastMarker.remove()
                    updateLine()
                })
                line = L.polyline([[lat, lon]], { color: "yellow", weight: 5 }).addTo(map)
            }

            // activeElements.push(currentLine, currentMarker)
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
