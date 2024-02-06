// Sourced from https://valhalla.github.io/valhalla/decoding/#javascript

/**
 * Decode a polyline string
 * @param {string} str Polyline string
 * @param {number} precision Precision
 * @returns {Array<[number, number]>} Coordinates in [lon, lat] format
 */
export const polylineDecode = (str, precision) => {
    const coordinates = []
    const factor = 10 ** precision
    let index = 0
    let lat = 0
    let lon = 0
    let shift = 0
    let result = 0
    let byte = null
    let latitudeChange
    let longitudeChange

    // Coordinates have variable length when encoded, so just keep
    // track of whether we've hit the end of the string. In each
    // loop iteration, a single coordinate is decoded.
    while (index < str.length) {
        // Reset shift, result, and byte
        byte = null
        shift = 0
        result = 0

        do {
            byte = str.charCodeAt(index++) - 63
            result |= (byte & 0x1f) << shift
            shift += 5
        } while (byte >= 0x20)

        latitudeChange = result & 1 ? ~(result >> 1) : result >> 1

        shift = result = 0

        do {
            byte = str.charCodeAt(index++) - 63
            result |= (byte & 0x1f) << shift
            shift += 5
        } while (byte >= 0x20)

        longitudeChange = result & 1 ? ~(result >> 1) : result >> 1

        lat += latitudeChange
        lon += longitudeChange

        coordinates.push([lon / factor, lat / factor])
    }

    return coordinates
}
