// Encoded Polyline Algorithm Format
// https://developers.google.com/maps/documentation/utilities/polylinealgorithm

/**
 * Round a number using Python2 algorithm.
 * @example
 * round_py2(0.5) // 1
 * round_py2(-0.5) // -1
 */
const roundPy2 = (value: number): number => (value + (value < 0 ? -0.5 : 0.5)) | 0

const encode = (delta: number, codes: number[]): void => {
    let coord = (delta << 1) ^ (delta >> 0x1f)
    do {
        const b = coord & 0x1f
        coord >>= 5
        codes.push(b + (coord ? 32 : 0) + 63)
    } while (coord)
}

/** Encode the given [longitude, latitude] coordinate pairs */
export const encodeLonLat = (coords: [number, number][], precision: number): string => {
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

/** Decode to [longitude, latitude] coordinate pairs */
export const decodeLonLat = (line: string, precision: number): [number, number][] => {
    const invFactor = 10 ** -precision
    const coords: [number, number][] = []
    let lat = 0
    let lon = 0
    for (let i = 0; i < line.length; ) {
        const decode = (): number => {
            let result = 0
            let shift = 1
            let code: number
            do {
                code = line.charCodeAt(i++) - 63
                result += (code & 0x1f) * shift
                shift <<= 5
            } while (code >= 0x20)
            return (result & 1 ? ~result : result) >> 1
        }
        lat += decode()
        lon += decode()
        coords.push([lon * invFactor, lat * invFactor])
    }
    return coords
}
