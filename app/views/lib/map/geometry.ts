import { Point } from "maplibre-gl"

/** Get the closest point on a segment */
export const closestPointOnSegment = (test: Point, start: Point, end: Point): Point => {
    const dx = end.x - start.x
    const dy = end.y - start.y
    if (dx === 0 && dy === 0) return new Point(start.x, start.y)

    // Calculate projection position (t) on line using dot product
    // t = ((test-start) * (end-start)) / |end-start|²
    const t = Math.max(
        0,
        Math.min(
            1,
            ((test.x - start.x) * dx + (test.y - start.y) * dy) / (dx ** 2 + dy ** 2),
        ),
    )
    return new Point(start.x + t * dx, start.y + t * dy)
}
