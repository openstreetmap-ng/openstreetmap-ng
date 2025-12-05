import type { PositionAnchor } from "maplibre-gl"

export const MARKER_ICON_ANCHOR: PositionAnchor = "bottom"

export type MarkerColor = "blue" | "green" | "red" | "new"

export const getMarkerIconElement = (color: MarkerColor, showShadow: boolean) => {
    const container = document.createElement("div")
    container.classList.add("marker-icon")
    if (showShadow) {
        const shadow = document.createElement("img")
        shadow.classList.add("marker-shadow")
        shadow.src = "/static/img/marker/shadow.webp"
        shadow.width = 41
        shadow.height = 41
        shadow.draggable = false
        container.appendChild(shadow)
    }
    const icon = document.createElement("img")
    icon.classList.add("marker-icon-inner")
    icon.src = `/static/img/marker/${color}.webp`
    icon.width = 25
    icon.height = 41
    icon.draggable = false
    container.appendChild(icon)
    // TODO: leaflet leftover
    // iconAnchor: [12, 41]
    return container
}
