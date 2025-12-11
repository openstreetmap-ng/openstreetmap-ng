// Encoded Polyline Algorithm Format
// https://developers.google.com/maps/documentation/utilities/polylinealgorithm

const CHUNK_BITS = 5
const CHUNK_MASK = (1 << CHUNK_BITS) - 1
const CONTINUATION_BIT = 1 << CHUNK_BITS
const ASCII_OFFSET = 63

/**
 * Round a number using Python2 algorithm.
 * @example
 * round_py2(0.5) // 1
 * round_py2(-0.5) // -1
 */
const roundPy2 = (value: number) => (value + (value < 0 ? -0.5 : 0.5)) | 0

export const encodeLonLat = (coords: [number, number][], precision: number) => {
    const factor = 10 ** precision
    let out = ""
    let prevLatInt = 0
    let prevLonInt = 0

    const encodeDelta = (delta: number) => {
        let coord = (delta << 1) ^ (delta >> 31) // Zigzag encoding
        while (coord >= CONTINUATION_BIT) {
            out += String.fromCharCode(
                ((coord & CHUNK_MASK) | CONTINUATION_BIT) + ASCII_OFFSET,
            )
            coord >>>= CHUNK_BITS
        }
        out += String.fromCharCode(coord + ASCII_OFFSET)
    }

    for (const [lon, lat] of coords) {
        const latInt = roundPy2(lat * factor)
        const lonInt = roundPy2(lon * factor)
        encodeDelta(latInt - prevLatInt)
        encodeDelta(lonInt - prevLonInt)
        prevLatInt = latInt
        prevLonInt = lonInt
    }
    return out
}

export const decodeLonLat = (line: string, precision: number) => {
    const len = line.length
    const invFactor = 1 / 10 ** precision
    const coords: [number, number][] = []
    let lat = 0
    let lon = 0
    let i = 0

    const decodeDelta = () => {
        let code: number
        let result = 0
        let shift = 0
        do {
            code = line.charCodeAt(i++) - ASCII_OFFSET
            result |= (code & CHUNK_MASK) << shift
            shift += CHUNK_BITS
        } while (code >= CONTINUATION_BIT)
        return (result >> 1) ^ -(result & 1) // Zigzag decode
    }

    while (i < len) {
        lat += decodeDelta()
        lon += decodeDelta()
        coords.push([lon * invFactor, lat * invFactor])
    }
    return coords
}
