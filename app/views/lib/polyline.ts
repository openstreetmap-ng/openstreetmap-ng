// Encoded Polyline Algorithm Format
// https://developers.google.com/maps/documentation/utilities/polylinealgorithm

export type Polyline = readonly (readonly [lon: number, lat: number])[]

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

export const polylineEquals = (
  a: Polyline | undefined,
  b: Polyline | undefined,
  precision: number,
) => {
  if (a === undefined) return b === undefined
  if (b === undefined) return false
  if (a.length !== b.length) return false

  const factor = 10 ** precision
  for (let i = 0; i < a.length; i++) {
    const pa = a[i]
    const pb = b[i]
    if (
      roundPy2(pa[0] * factor) !== roundPy2(pb[0] * factor) ||
      roundPy2(pa[1] * factor) !== roundPy2(pb[1] * factor)
    )
      return false
  }
  return true
}

export const polylineEncode = (line: Polyline, precision: number) => {
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

  for (const [lon, lat] of line) {
    const latInt = roundPy2(lat * factor)
    const lonInt = roundPy2(lon * factor)
    encodeDelta(latInt - prevLatInt)
    encodeDelta(lonInt - prevLonInt)
    prevLatInt = latInt
    prevLonInt = lonInt
  }
  return out
}

export const polylineDecode = (line: string, precision: number) => {
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
  return coords satisfies Polyline
}
