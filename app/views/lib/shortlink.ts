import type { LonLatZoom } from "@lib/map/state"
import { modulo } from "@std/math/modulo"
import { getBitMasks } from "./shortlink.macro" with { type: "macro" }

/** 64 chars to encode 6 bits */
const CODE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~"

// Normalize lon/lat to 32-bit unsigned
const LON_TO_UINT32 = 2 ** 32 / 360
const LAT_TO_UINT32 = 2 ** 32 / 180

const BIT_MASKS = getBitMasks()

/** Encode coordinates to OSM shortlink code */
export const shortLinkEncode = ({ lon, lat, zoom }: LonLatZoom) => {
    const n = (zoom | 0) + 8
    const r = n % 3
    const d = Math.ceil(n / 3)

    const x = BigInt((modulo(lon + 180, 360) * LON_TO_UINT32) | 0)
    const y = BigInt(((lat + 90) * LAT_TO_UINT32) | 0)

    // Interleave x/y bits (Morton code)
    let c = 0n
    for (const mask of BIT_MASKS) {
        c = (c << 2n) | (x & mask ? 2n : 0n) | (y & mask ? 1n : 0n)
    }

    let result = ""
    for (let i = 0; i < d; i++)
        result += CODE[Number((c >> BigInt(58 - 6 * i)) & 0x3fn)]
    for (let i = 0; i < r; i++) result += "-"
    return result
}
