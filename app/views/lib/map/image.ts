import { NoteStatus } from "@lib/proto/note_pb"
import type { Map as MaplibreMap } from "maplibre-gl"

const MARKER_IMAGES = {
  "marker-open": "/static/img/marker/open.webp",
  "marker-closed": "/static/img/marker/closed.webp",
  "marker-hidden": "/static/img/marker/hidden.webp",
  "marker-blue": "/static/img/marker/blue.webp",
  "marker-red": "/static/img/marker/red.webp",
} as const

type MarkerImageName = keyof typeof MARKER_IMAGES

export const NOTE_STATUS_MARKERS: Record<NoteStatus, MarkerImageName> = {
  [NoteStatus.open]: "marker-open",
  [NoteStatus.closed]: "marker-closed",
  [NoteStatus.hidden]: "marker-hidden",
}

const images = new Map<MarkerImageName, HTMLImageElement>()

export const loadMapImage = (
  map: MaplibreMap,
  name: MarkerImageName,
  successCallback?: () => void,
) => {
  let image = images.get(name)
  if (!image) {
    image = new Image()
    image.src = MARKER_IMAGES[name]
    image.decoding = "async"
    images.set(name, image)
  }
  const addImage = () => {
    if (!map.hasImage(name)) {
      console.debug("MapImage: Adding", name)
      map.addImage(name, image)
    }
    successCallback?.()
  }
  if (image.complete) addImage()
  else image.addEventListener("load", addImage, { once: true })
}
