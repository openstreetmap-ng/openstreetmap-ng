import type { Map as MaplibreMap } from "maplibre-gl"

export const markerOpenImageUrl = "/static/img/marker/open.webp"
export const markerClosedImageUrl = "/static/img/marker/closed.webp"
export const markerRedImageUrl = "/static/img/marker/red.webp"

const images: Map<string, HTMLImageElement> = new Map()

/** Load an image into the map context */
export const loadMapImage = (map: MaplibreMap, name: string, url: string): void => {
    let image: HTMLImageElement
    if (!images.has(name)) {
        image = new Image()
        image.src = url
        image.decoding = "async"
        images.set(name, image)
    } else {
        image = images.get(name)
    }
    const addImage = () => {
        if (map.hasImage(name)) return
        console.debug("Adding map image", name)
        map.addImage(name, image)
    }
    if (image.complete) addImage()
    else image.addEventListener("load", () => addImage(), { once: true })
}
