import i18next from "i18next"
import type { LngLatBounds, Map as MaplibreMap } from "maplibre-gl"
import { getLngLatBoundsIntersection } from "./_utils"

// https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob#quality
const imageQuality = 0.98

/**
 * Export the map image
 * @example
 * exportMapImage("image/png", [48.208889, 16.3725, 48.209444, 16.373056], 12, baseLayer)
 * // => Blob { size: 123456, type: "image/png" }
 */
export const exportMapImage = async (
    mimeType: string,
    map: MaplibreMap,
    filterBounds: LngLatBounds | null,
    attribution: boolean,
): Promise<Blob> => {
    const sourceCanvas = map.getCanvas()
    console.debug("exportMapImage", [sourceCanvas.width, sourceCanvas.height], mimeType, imageQuality)
    let exportCanvas = document.createElement("canvas")
    exportCanvas.width = sourceCanvas.width
    exportCanvas.height = sourceCanvas.height
    let ctx = exportCanvas.getContext("2d", { alpha: false })
    ctx.drawImage(sourceCanvas, 0, 0)

    if (filterBounds) {
        const mapBounds = map.getBounds()
        console.debug("Filtering map bounds", mapBounds, "with", filterBounds)
        const { top, left, bottom, right } = getImageTrim(
            map,
            exportCanvas.width,
            exportCanvas.height,
            mapBounds,
            filterBounds,
        )
        const trimCanvas = document.createElement("canvas")
        trimCanvas.width = exportCanvas.width - (left + right)
        trimCanvas.height = exportCanvas.height - (top + bottom)
        ctx = trimCanvas.getContext("2d", { alpha: false })
        ctx.drawImage(
            exportCanvas,
            left,
            top,
            trimCanvas.width,
            trimCanvas.height,
            0,
            0,
            trimCanvas.width,
            trimCanvas.height,
        )
        exportCanvas = trimCanvas
    }
    if (attribution) {
        const attributionText = `© ${i18next.t("javascripts.map.openstreetmap_contributors")}`
        const fontSize = Math.round(window.devicePixelRatio * 16)

        const ctx = exportCanvas.getContext("2d", { alpha: false })
        ctx.font = `500 ${fontSize}px sans-serif`
        ctx.textAlign = "left"
        ctx.textBaseline = "top"

        const textMetrics = ctx.measureText(attributionText)
        const textWidth = textMetrics.width
        const textHeight = fontSize * 0.9

        const padding = Math.round(window.devicePixelRatio * 10)
        const xPos = exportCanvas.width - textWidth - padding * 2
        const yPos = exportCanvas.height - textHeight - padding * 2

        ctx.fillStyle = "white"
        ctx.fillRect(xPos, yPos, textWidth + padding * 2, textHeight + padding * 2)
        ctx.fillStyle = "black"
        ctx.fillText(attributionText, xPos + padding, yPos + padding, textWidth)
    }

    // Export the canvas to an image
    return new Promise((resolve, reject) => {
        exportCanvas.toBlob(
            (blob) => {
                if (blob) resolve(blob)
                else reject("Failed to export the map image")
            },
            mimeType,
            imageQuality,
        )
    })
}

/** Calculate the offsets for trimming the exported image */
const getImageTrim = (
    map: MaplibreMap,
    width: number,
    height: number,
    mapBounds: LngLatBounds,
    filterBounds: LngLatBounds,
): { top: number; left: number; bottom: number; right: number } => {
    filterBounds = getLngLatBoundsIntersection(mapBounds, filterBounds)
    if (filterBounds.isEmpty()) {
        return { top: 0, left: 0, bottom: 0, right: 0 }
    }
    const bottomLeft = map.project(filterBounds.getSouthWest())
    const topRight = map.project(filterBounds.getNorthEast())
    const ratio = window.devicePixelRatio
    return {
        top: Math.ceil(topRight.y * ratio),
        left: Math.ceil(bottomLeft.x * ratio),
        bottom: Math.ceil(height - bottomLeft.y * ratio),
        right: Math.ceil(width - topRight.x * ratio),
    }
}
