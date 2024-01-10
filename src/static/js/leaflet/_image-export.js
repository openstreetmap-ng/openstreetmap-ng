import * as L from "leaflet"

const MAX_ZOOM = 25
const TILE_SIZE = 256
const OPTIMAL_EXPORT_RESOLUTION = 1024
const EARTH_RADIUS = 6371000
const EARTH_CIRCUMFERENCE = 40030173 // 2 * Math.PI * EARTH_RADIUS

// https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob#quality
const IMAGE_QUALITY = 0.95

export const getOptimalExportParams = (bounds) => {
    let [minLat, minLon, maxLat, maxLon] = bounds
    // The bounds cross the antimeridian
    if (minLon > maxLon) maxLon += 360

    const sizeInDegrees = L.point(maxLon - minLon, maxLat - minLat)
    const sizeInRadians = sizeInDegrees.multiplyBy(Math.PI / 180)
    const sizeInMeters = sizeInRadians.multiplyBy(EARTH_RADIUS)
    const xProportion = sizeInMeters.x / EARTH_CIRCUMFERENCE
    const yProportion = sizeInMeters.y / EARTH_CIRCUMFERENCE

    let optimalZoom = MAX_ZOOM

    // Find the zoom level that closest matches the optimal export resolution
    for (let z = 0; z < MAX_ZOOM; z++) {
        const yResolution = TILE_SIZE * 2 ** z * yProportion
        if (yResolution < OPTIMAL_EXPORT_RESOLUTION * (2 / 3)) continue
        optimalZoom = z
    }

    const optimalEarthResolution = TILE_SIZE * 2 ** optimalZoom
    const optimalXResolution = optimalEarthResolution * xProportion
    const optimalYResolution = optimalEarthResolution * yProportion

    return { zoom: optimalZoom, xResolution: optimalXResolution, yResolution: optimalYResolution }
}

const getTileCoords = (lon, lat, zoom) => {
    const n = 2 ** zoom
    const x = Math.floor(((lon + 180) / 360) * n)
    const y = Math.floor(
        ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * n,
    )
    return { x, y }
}

const getLatLonFromTileCoords = (x, y, zoom) => {
    const n = 2 ** zoom
    const lon = (x / n) * 360 - 180
    const lat = (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) * 180) / Math.PI
    return { lat, lon }
}

const wrapTileCoords = (x, y, zoom) => {
    const n = 2 ** zoom
    return { x: ((x % n) + n) % n, y: ((y % n) + n) % n }
}

export const exportMapImage = async (format, bounds, zoom, baseLayer) => {
    let [minLat, minLon, maxLat, maxLon] = bounds
    // The bounds cross the antimeridian
    if (minLon > maxLon) maxLon += 360

    const sizeInDegrees = L.point(maxLon - minLon, maxLat - minLat)
    const sizeInRadians = sizeInDegrees.multiplyBy(Math.PI / 180)
    const sizeInMeters = sizeInRadians.multiplyBy(EARTH_RADIUS)
    const xProportion = sizeInMeters.x / EARTH_CIRCUMFERENCE
    const yProportion = sizeInMeters.y / EARTH_CIRCUMFERENCE

    const earthResolution = TILE_SIZE * 2 ** zoom
    const xResolution = earthResolution * xProportion
    const yResolution = earthResolution * yProportion

    const minTileCoords = getTileCoords(minLon, maxLat, zoom)
    const maxTileCoords = getTileCoords(maxLon, minLat, zoom)

    // Calculate the pixel position for trimming
    const wrappedMinTileCoords = wrapTileCoords(minTileCoords.x, minTileCoords.y, zoom)
    const minTopLeft = getLatLonFromTileCoords(wrappedMinTileCoords.x, wrappedMinTileCoords.y, zoom)
    const wrappedMinEndTileCoords = wrapTileCoords(minTileCoords.x + 1, minTileCoords.y + 1, zoom)
    const minBottomRight = getLatLonFromTileCoords(wrappedMinEndTileCoords.x, wrappedMinEndTileCoords.y, zoom)
    const wrappedMaxTileCoords = wrapTileCoords(maxTileCoords.x, maxTileCoords.y, zoom)
    const maxTopLeft = getLatLonFromTileCoords(wrappedMaxTileCoords.x, wrappedMaxTileCoords.y, zoom)
    const wrappedMaxEndTileCoords = wrapTileCoords(maxTileCoords.x + 1, maxTileCoords.y + 1, zoom)
    const maxBottomRight = getLatLonFromTileCoords(wrappedMaxEndTileCoords.x, wrappedMaxEndTileCoords.y, zoom)

    const topOffset = Math.round(((maxLat - minTopLeft.lat) / (minBottomRight.lat - minTopLeft.lat)) * TILE_SIZE)
    const leftOffset = Math.round(((minLon - minTopLeft.lon) / (minBottomRight.lon - minTopLeft.lon)) * TILE_SIZE)
    const bottomOffset = Math.round(((maxBottomRight.lat - minLat) / (maxBottomRight.lat - maxTopLeft.lat)) * TILE_SIZE)
    const rightOffset = Math.round(((maxBottomRight.lon - maxLon) / (maxBottomRight.lon - maxTopLeft.lon)) * TILE_SIZE)

    // Create a canvas to draw the tiles on
    const canvas = document.createElement("canvas")
    canvas.width = (maxTileCoords.x - minTileCoords.x + 1) * TILE_SIZE - leftOffset - rightOffset
    canvas.height = (maxTileCoords.y - minTileCoords.y + 1) * TILE_SIZE - topOffset - bottomOffset
    const ctx = canvas.getContext("2d")

    const fetchTilePromise = (x, y) => {
        return new Promise((resolve, reject) => {
            const img = new Image()
            img.crossOrigin = "anonymous"
            img.onload = () => {
                const dx = (x - minTileCoords.x) * TILE_SIZE - leftOffset
                const dy = (y - minTileCoords.y) * TILE_SIZE - topOffset
                ctx.drawImage(img, dx, dy)
                resolve()
            }
            img.onerror = () => {
                reject(`Failed to load tile at x=${x}, y=${y}, z=${zoom}`)
            }
            img.src = baseLayer.getTileUrl({ x, y, z: zoom })
        })
    }

    // Fetch tiles in parallel
    const fetchTilesPromises = []
    for (let x = minTileCoords.x; x <= maxTileCoords.x; x++) {
        for (let y = minTileCoords.y; y <= maxTileCoords.y; y++) {
            const wrapped = wrapTileCoords(x, y, zoom)
            fetchTilesPromises.push(fetchTilePromise(wrapped.x, wrapped.y))
        }
    }

    await Promise.all(fetchTilesPromises)

    // Export the canvas to an image
    return new Promise((resolve, reject) => {
        canvas.toBlob(
            (blob) => {
                if (blob) resolve(blob)
                else reject("Failed to export the map image")
            },
            format,
            IMAGE_QUALITY,
        )
    })
}
