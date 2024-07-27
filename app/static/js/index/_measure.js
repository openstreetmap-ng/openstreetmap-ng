import { qsEncode, qsParse } from "../_qs.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import * as L from "leaflet"

export const getMeasuringController = (map) => {
    const markers = []
    var line = null
    var currentMarker = null

    const updateLine = () => {
        const latLngs = markers.map((marker) => marker.getLatLng())
        console.log(latLngs)
        // skip first marker
        if (currentMarker.getLatLng().lat != 100) {
            latLngs.push(currentMarker.getLatLng())
        }

        line.setLatLngs(latLngs)
    }

    const markerFactory = (color) =>
        L.marker(L.latLng(100, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        })
            .addTo(map)
            .on("drag", updateLine)

    const mouseMove = (e) => {
        // skip first marker
        if (currentMarker.getLatLng().lat != 100) {
            const marker = markerFactory("blue")
                .setLatLng(currentMarker.getLatLng())
                .addEventListener("click", () => {
                    markers.splice(markers.indexOf(marker), 1);
                    marker.remove()
                    updateLine()
                })
            markers.push(marker)
        }
        currentMarker.setLatLng(e.latlng)
        line.addLatLng(e.latlng)
    }

    return {
        load: () => {
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.pos) {
                const [lat, lon] = searchParams.pos.split(",")
                markers.push(markerFactory("yellow").setLatLng([lat, lon]))
                currentMarker = markerFactory("yellow")
                line = L.polyline([[lat, lon]], { color: "yellow" }).addTo(map)
            }

            // activeElements.push(currentLine, currentMarker)
            map.addEventListener("click", mouseMove)
        },
        unload: () => {
            // activeElements.forEach((marker, index) => {
            //     marker.remove()
            //     delete activeElements[index]
            // })
            map.removeEventListener("click", mouseMove)
        },
    }
}
