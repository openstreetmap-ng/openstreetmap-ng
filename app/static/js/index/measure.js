import { qsEncode, qsParse } from "../_qs.js"
import { getMarkerIcon } from "../leaflet/_utils.js"

export const getMeasuringController = (map) => {
    var activeMarkers = []
    const markerFactory = (color) =>
        L.marker(L.latLng(0, 0), {
            icon: getMarkerIcon(color, true),
            draggable: true,
            autoPan: true,
        }).addTo(map)

    return {
        load: () => {
            const searchParams = qsParse(location.search.substring(1))
            if (searchParams.pos) {
                const [lat, lon] = searchParams.pos.split(",")
                activeMarkers.push(markerFactory("yellow").setLatLng([lat, lon]))
            }
        },
        unload: () => {
            activeMarkers.forEach((marker, index) => {
                marker.remove()
                delete activeMarkers[index]
            })
        },
    }
}
