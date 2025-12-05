import type { LonLatZoom } from "@lib/map/state"
import { memoize } from "@lib/memoize"
import { mod } from "@lib/utils"

/** 64 chars to encode 6 bits */
const CODE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~"

// Bit masks for coordinate interleaving (Morton code / Z-order curve)
const getBitMasks = memoize(() =>
    Array.from({ length: 32 }, (_, i) => 1n << BigInt(31 - i)),
)

// (2^32)/360 and (2^32)/180: normalize lon/lat to 32-bit unsigned
const LON_TO_INT32 = 11930464.711111112
const LAT_TO_INT32 = 23860929.422222223

/** Encode coordinates to OSM shortlink code */
export const shortLinkEncode = ({ lon, lat, zoom }: LonLatZoom) => {
    const z = (zoom | 0) + 8
    const d = Math.ceil(z / 3)
    const r = z % 3

    const x = BigInt((mod(lon + 180, 360) * LON_TO_INT32) | 0)
    const y = BigInt(((lat + 90) * LAT_TO_INT32) | 0)

    // Interleave x/y bits (Morton code)
    let c = 0n
    for (const mask of getBitMasks()) {
        c = (c << 2n) | (x & mask ? 2n : 0n) | (y & mask ? 1n : 0n)
    }

    let result = ""
    for (let i = 0; i < d; i++)
        result += CODE[Number((c >> BigInt(58 - 6 * i)) & 0x3fn)]
    for (let i = 0; i < r; i++) result += "-"
    return result
}
