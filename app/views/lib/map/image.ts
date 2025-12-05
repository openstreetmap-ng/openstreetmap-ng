import type { Map as MaplibreMap } from "maplibre-gl"

const MARKER_IMAGES = {
    "marker-open": "/static/img/marker/open.webp",
    "marker-closed": "/static/img/marker/closed.webp",
    "marker-hidden": "/static/img/marker/hidden.webp",
    "marker-blue": "/static/img/marker/blue.webp",
    "marker-red": "/static/img/marker/red.webp",
} as const

type MarkerImageName = keyof typeof MARKER_IMAGES

export const NOTE_STATUS_MARKERS = {
    open: "marker-open",
    closed: "marker-closed",
    hidden: "marker-hidden",
} as const satisfies Record<string, MarkerImageName>

export type NoteStatus = keyof typeof NOTE_STATUS_MARKERS

const images = new Map<MarkerImageName, HTMLImageElement>()

/** Load an image into the map context */
export const loadMapImage = (
    map: MaplibreMap,
    name: MarkerImageName,
    successCallback?: () => void,
): void => {
    let image = images.get(name)
    if (!image) {
        image = new Image()
        image.src = MARKER_IMAGES[name]
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
