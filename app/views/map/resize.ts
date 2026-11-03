import type { Map as MaplibreMap } from "maplibre-gl"

/** Keep the opposite map edge in place when a mobile sidebar changes its bounds. */
export const resizeMapForSidebar = (
  map: MaplibreMap,
  previousBounds: DOMRectReadOnly,
  preservePosition: boolean,
) => {
  const container = map.getContainer()
  const bounds = container.getBoundingClientRect()
  const shouldPan =
    preservePosition &&
    !map.isMoving() &&
    bounds.width === previousBounds.width &&
    (bounds.height !== previousBounds.height || bounds.top !== previousBounds.top)

  if (!shouldPan) {
    map.resize()
    return
  }

  const previousBottom = previousBounds.top + previousBounds.height
  const bottom = bounds.top + bounds.height
  // A panel above the map keeps its bottom edge fixed, and vice versa.
  // If both edges move, use the middle of the area visible in both layouts.
  const screenY =
    bounds.top === previousBounds.top
      ? previousBounds.top
      : bottom === previousBottom
        ? previousBottom
        : (Math.max(bounds.top, previousBounds.top) + Math.min(bottom, previousBottom)) / 2
  const point: [number, number] = [previousBounds.width / 2, screenY - previousBounds.top]
  const anchor = map.unproject(point)
  const projected = map.project(anchor)
  // A globe's sky has no geographic point to lock. Its unproject result is
  // clamped to the horizon; do not pan towards that unrelated location.
  const onSurface = Math.hypot(projected.x - point[0], projected.y - point[1]) <= 1

  map.resize()

  const target: [number, number] = [bounds.width / 2, screenY - bounds.top]
  const projectedTarget = map.project(map.unproject(target))
  const targetOnSurface =
    Math.hypot(projectedTarget.x - target[0], projectedTarget.y - target[1]) <= 1

  if (onSurface && targetOnSurface) {
    const center = map.project(map.getCenter())
    map.panTo(anchor, {
      offset: [target[0] - center.x, target[1] - center.y],
      duration: 0,
    })
  }
}
