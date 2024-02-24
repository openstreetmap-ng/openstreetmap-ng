import * as L from "leaflet"

const maxZoom = 25
const tileSize = 256
const optimalExportResolution = Math.max(1024, innerHeight)
const earthRadius = 6371000
const earthCircumference = 40030173 // 2 * Math.PI * EARTH_RADIUS

// TODO: add information that only base layer is exported, no markers etc.

// https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob#quality
const imageQuality = 0.98

/**
 * Returns the optimal zoom level and resolution for exporting the map image
 * @param {number[]} bounds Map bounds in the format [minLon, minLat, maxLon, maxLat]
 */
export const getOptimalExportParams = (bounds) => {
    let [minLon, minLat, maxLon, maxLat] = bounds
    // The bounds cross the antimeridian
    while (minLon > maxLon) maxLon += 360

    const sizeInDegrees = L.point(maxLon - minLon, maxLat - minLat)
    const sizeInRadians = sizeInDegrees.multiplyBy(Math.PI / 180)
    const sizeInMeters = sizeInRadians.multiplyBy(earthRadius)
    const xProportion = sizeInMeters.x / earthCircumference
    const yProportion = sizeInMeters.y / earthCircumference

    let optimalZoom = maxZoom
    let yResolution = tileSize * 2 ** maxZoom * yProportion
    const yResolutionTarget = optimalExportResolution * (2 / 3)

    // Find the zoom level that closest matches the optimal export resolution
    while (yResolution > yResolutionTarget && optimalZoom > 0) {
        optimalZoom--
        yResolution /= 2
    }

    const optimalEarthResolution = tileSize * 2 ** optimalZoom
    const optimalXResolution = optimalEarthResolution * xProportion
    const optimalYResolution = optimalEarthResolution * yProportion

    return { zoom: optimalZoom, xResolution: optimalXResolution, yResolution: optimalYResolution }
}

/**
 * Get tile coordinates for the given coordinates and zoom level
 * @param {number} lon Longitude
 * @param {number} lat Latitude
 * @param {number} zoom Zoom level
 * @returns {{ x: number, y: number }} Tile coordinates
 * @example
 * getTileCoords(16.3725, 48.208889, 12)
 * // => { x: 2234, y: 1420 }
 */
const getTileCoords = (lon, lat, zoom) => {
    const n = 2 ** zoom
    const x = Math.floor(((lon + 180) / 360) * n)
    const y = Math.floor(
        ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * n,
    )
    return { x, y }
}

/**
 * Get coordinates for the given tile coordinates and zoom level
 * @param {number} x Tile X coordinate
 * @param {number} y Tile Y coordinate
 * @param {number} zoom Zoom level
 * @returns {{ lon: number, lat: number }} Coordinates
 * @example
 * getLatLonFromTileCoords(2234, 1420, 12)
 * // => { lon: 16.3725, lat: 48.208889 }
 */
const getLatLonFromTileCoords = (x, y, zoom) => {
    const n = 2 ** zoom
    const lon = (x / n) * 360 - 180
    const lat = (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) * 180) / Math.PI
    return { lat, lon }
}

/**
 * Wrap the tile coordinates to the valid range at the given zoom level
 * @param {number} x Tile X coordinate
 * @param {number} y Tile Y coordinate
 * @param {number} zoom Zoom level
 * @returns {{ x: number, y: number }} Wrapped tile coordinates
 * @example
 * wrapTileCoords(2234, 1420, 10)
 * // => { x: 186, y: 396 }
 */
const wrapTileCoords = (x, y, zoom) => {
    const n = 2 ** zoom
    return { x: ((x % n) + n) % n, y: ((y % n) + n) % n }
}

/**
 * Export the map image
 * @param {string} mimeType Image MIME type
 * @param {number[]} bounds Map bounds in the format [minLon, minLat, maxLon, maxLat]
 * @param {number} zoom Zoom level
 * @param {L.TileLayer} baseLayer Base layer
 * @returns {Promise<Blob>} Image blob
 * @example
 * exportMapImage("image/png", [48.208889, 16.3725, 48.209444, 16.373056], 12, baseLayer)
 * // => Blob { size: 123456, type: "image/png" }
 */
export const exportMapImage = async (mimeType, bounds, zoom, baseLayer) => {
    console.debug("exportMapImage", mimeType, bounds, zoom, baseLayer)

    let [minLon, minLat, maxLon, maxLat] = bounds
    // The bounds cross the antimeridian
    while (minLon > maxLon) maxLon += 360

    // Clamp latitudes to avoid numerical errors
    minLat = Math.max(minLat, -85)
    maxLat = Math.min(maxLat, 85)

    const minTileCoords = getTileCoords(minLon, maxLat, zoom)
    const maxTileCoords = getTileCoords(maxLon, minLat, zoom)

    const { topOffset, leftOffset, bottomOffset, rightOffset } = calculateTrimOffsets(
        minLon,
        minLat,
        maxLon,
        maxLat,
        zoom,
        minTileCoords,
        maxTileCoords,
    )

    // Create a canvas to draw the tiles on
    const canvas = document.createElement("canvas")
    canvas.width = (maxTileCoords.x - minTileCoords.x + 1) * tileSize - leftOffset - rightOffset
    canvas.height = (maxTileCoords.y - minTileCoords.y + 1) * tileSize - topOffset - bottomOffset
    const ctx = canvas.getContext("2d", { alpha: false })

    // Extract base layer url and options
    const baseLayerUrl = baseLayer._url
    const baseLayerOptions = baseLayer.options

    const fetchTilePromise = (x, y) => {
        return new Promise((resolve, reject) => {
            const wrapped = wrapTileCoords(x, y, zoom)
            const img = new Image()
            img.crossOrigin = "anonymous"
            img.onload = () => {
                const dx = (x - minTileCoords.x) * tileSize - leftOffset
                const dy = (y - minTileCoords.y) * tileSize - topOffset
                ctx.drawImage(img, dx, dy)
                resolve()
            }
            img.onerror = () => {
                reject(`Failed to load tile at x=${x}, y=${y}, z=${zoom}`)
            }
            img.src = L.Util.template(baseLayerUrl, L.Util.extend({ x: wrapped.x, y, z: zoom }, baseLayerOptions))
        })
    }

    // Fetch tiles in parallel
    const fetchTilesPromises = []
    for (let x = minTileCoords.x; x <= maxTileCoords.x; x++) {
        for (let y = minTileCoords.y; y <= maxTileCoords.y; y++) {
            fetchTilesPromises.push(fetchTilePromise(x, y))
        }
    }

    console.log("Fetching", fetchTilesPromises.length, "tiles...")
    await Promise.all(fetchTilesPromises)
    console.log("Finished fetching tiles")

    // Export the canvas to an image
    return new Promise((resolve, reject) => {
        canvas.toBlob(
            (blob) => {
                if (blob) resolve(blob)
                else reject("Failed to export the map image")
            },
            mimeType,
            imageQuality,
        )
    })
}

/**
 * Calculate the offsets for trimming the exported image
 * @param {number} minLon Minimum longitude
 * @param {number} minLat Minimum latitude
 * @param {number} maxLon Maximum longitude
 * @param {number} maxLat Maximum latitude
 * @param {number} zoom Zoom level
 * @param {{ x: number, y: number }} minTileCoords Minimum tile coordinates
 * @param {{ x: number, y: number }} maxTileCoords Maximum tile coordinates
 */
const calculateTrimOffsets = (minLon, minLat, maxLon, maxLat, zoom, minTileCoords, maxTileCoords) => {
    const minTopLeft = getLatLonFromTileCoords(minTileCoords.x, minTileCoords.y, zoom)
    const minBottomRight = getLatLonFromTileCoords(minTileCoords.x + 1, minTileCoords.y + 1, zoom)
    const maxTopLeft = getLatLonFromTileCoords(maxTileCoords.x, maxTileCoords.y, zoom)
    const maxBottomRight = getLatLonFromTileCoords(maxTileCoords.x + 1, maxTileCoords.y + 1, zoom)

    const topOffset = Math.round(((maxLat - minTopLeft.lat) / (minBottomRight.lat - minTopLeft.lat)) * tileSize)
    const leftOffset = Math.round(((minLon - minTopLeft.lon) / (minBottomRight.lon - minTopLeft.lon)) * tileSize)
    const bottomOffset = Math.round(((maxBottomRight.lat - minLat) / (maxBottomRight.lat - maxTopLeft.lat)) * tileSize)
    const rightOffset = Math.round(((maxBottomRight.lon - maxLon) / (maxBottomRight.lon - maxTopLeft.lon)) * tileSize)

    return { topOffset, leftOffset, bottomOffset, rightOffset }
}
