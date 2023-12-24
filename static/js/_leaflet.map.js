import * as L from "leaflet"

export const getMarkerIcon = (url) => {
    return L.icon({
        iconUrl: url || "/static/img/marker/red.webp",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowUrl: "/static/img/marker/shadow.webp",
        shadowSize: [41, 41],
    })
}
