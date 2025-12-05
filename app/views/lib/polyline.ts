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

const encode = (delta: number, codes: number[]) => {
    let coord = (delta << 1) ^ (delta >> 31) // Zigzag encoding
    do {
        const b = coord & CHUNK_MASK
        coord >>= CHUNK_BITS
        codes.push(b + (coord ? CONTINUATION_BIT : 0) + ASCII_OFFSET)
    } while (coord)
}

export const encodeLonLat = (coords: [number, number][], precision: number) => {
    const factor = 10 ** precision
    const codes: number[] = []
    let prevLatInt = 0
    let prevLonInt = 0
    for (const [lon, lat] of coords) {
        const latInt = roundPy2(lat * factor)
        const lonInt = roundPy2(lon * factor)
        encode(latInt - prevLatInt, codes)
        encode(lonInt - prevLonInt, codes)
        prevLatInt = latInt
        prevLonInt = lonInt
    }
    return String.fromCharCode(...codes)
}

export const decodeLonLat = (line: string, precision: number) => {
    const invFactor = 10 ** -precision
    const coords: [number, number][] = []
    let lat = 0
    let lon = 0
    for (let i = 0; i < line.length; ) {
        const decode = () => {
            let result = 0
            let shift = 1
            let code: number
            do {
                code = line.charCodeAt(i++) - ASCII_OFFSET
                result += (code & CHUNK_MASK) * shift
                shift <<= CHUNK_BITS
            } while (code >= CONTINUATION_BIT)
            return (result & 1 ? ~result : result) >> 1
        }
        lat += decode()
        lon += decode()
        coords.push([lon * invFactor, lat * invFactor])
    }
    return coords
}
