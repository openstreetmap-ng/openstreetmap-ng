import type { LonLatZoom } from "@lib/map/state"
import { memoize } from "@lib/memoize"
import { mod } from "@lib/utils"

/**
 * Encode a coordinate and zoom level to a short link code
 * @example
 * shortLinkEncode(5.123, 10.456, 17)
 * // => "wF7ZdNbjU-"
 */
export const shortLinkEncode = ({ lon, lat, zoom }: LonLatZoom): string => {
    const z = (zoom | 0) + 8
    const d = Math.ceil(z / 3)
    const r = z % 3

    const x = BigInt((mod(lon + 180, 360) * 11930464.711111112) | 0) // (2 ** 32) / 360
    const y = BigInt(((lat + 90) * 23860929.422222223) | 0) // (2 ** 32) / 180

    let c = 0n
    for (const mask of getBitMasks()) {
        // noinspection JSBitwiseOperatorUsage
        c = (c << 2n) | (x & mask ? 2n : 0n) | (y & mask ? 1n : 0n)
    }

    let result = ""
    for (let i = 0; i < d; i++)
        result += CODE[Number((c >> BigInt(58 - 6 * i)) & 0x3fn)]
    for (let i = 0; i < r; i++) result += "-"
    return result
}

const getBitMasks = memoize(() =>
    Array.from({ length: 32 }, (_, i) => 1n << BigInt(31 - i)),
)

/** 64 chars to encode 6 bits */
const CODE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~"
