import type { Map as MaplibreMap } from "maplibre-gl"

export const markerOpenImageUrl = "/static/img/marker/open.webp"
export const markerClosedImageUrl = "/static/img/marker/closed.webp"
export const markerBlueImageUrl = "/static/img/marker/blue.webp"
export const markerRedImageUrl = "/static/img/marker/red.webp"

const images: Map<string, HTMLImageElement> = new Map()

/** Load an image into the map context */
export const loadMapImage = (map: MaplibreMap, name: string, url: string, successCallback?: () => void): void => {
    let image = images.get(name)
    if (!image) {
        image = new Image()
        image.src = url
        image.decoding = "async"
        images.set(name, image)
    }
    const addImage = () => {
        if (!map.hasImage(name)) {
            console.debug("Adding map image", name)
            map.addImage(name, image)
        }
        successCallback?.()
    }
    if (image.complete) addImage()
    else image.addEventListener("load", () => addImage(), { once: true })
}
