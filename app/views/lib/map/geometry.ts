import { clamp } from "@std/math/clamp"
import { Point } from "maplibre-gl"

const WORLD_WIDTH_DEGREES = 360

/**
 * Return the copy of `lng` closest to `referenceLng`.
 *
 * MapLibre accepts unwrapped longitudes in GeoJSON. Keeping adjacent vertices in
 * the same world copy prevents globe mode from choosing the long way around the
 * antimeridian for short segments such as 179°E → 179°W.
 */
export const unwrapLongitude = (lng: number, referenceLng: number) =>
  lng + Math.round((referenceLng - lng) / WORLD_WIDTH_DEGREES) * WORLD_WIDTH_DEGREES

/** Get the closest point on a segment */
export const closestPointOnSegment = (test: Point, start: Point, end: Point) => {
  const dx = end.x - start.x
  const dy = end.y - start.y
  if (dx === 0 && dy === 0) return new Point(start.x, start.y)

  // Calculate projection position (t) on line using dot product
  // t = ((test-start) * (end-start)) / |end-start|²
  const t = clamp(
    ((test.x - start.x) * dx + (test.y - start.y) * dy) / (dx ** 2 + dy ** 2),
    0,
    1,
  )
  return new Point(start.x + t * dx, start.y + t * dy)
}
