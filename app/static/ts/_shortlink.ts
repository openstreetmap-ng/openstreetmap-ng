import { mod } from "./_utils"
import type { LonLatZoom } from "./leaflet/_map-utils"

/**
 * Encode a coordinate and zoom level to a short link code
 * @example
 * shortLinkEncode(5.123, 10.456, 17)
 * // => "wF7ZdNbjU-"
 */
export const shortLinkEncode = ({ lon, lat, zoom }: LonLatZoom): string => {
    const z = (zoom | 0) + 8
    const d = Math.ceil((z + 8) / 3)
    const r = (z + 8) % 3

    const x = BigInt((mod(lon + 180, 360) * 11930464.711111112) | 0) // (2 ** 32) / 360
    const y = BigInt(((lat + 90) * 23860929.422222223) | 0) // (2 ** 32) / 180

    let c = 0n
    for (const mask of bitMasks) {
        // noinspection JSBitwiseOperatorUsage
        c = (c << 2n) | (x & mask ? 2n : 0n) | (y & mask ? 1n : 0n)
    }

    const buffer = new Array(d + r)
    for (let i = 0; i < d; i++) {
        buffer[i] = code[Number((c >> BigInt(58 - 6 * i)) & 0x3fn)]
    }
    for (let i = d; i < buffer.length; i++) {
        buffer[i] = "-"
    }

    return buffer.join("")
}

/** 64 chars to encode 6 bits */
const code = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~"
const bitMasks = Object.freeze([
    2147483648n,
    1073741824n,
    536870912n,
    268435456n,
    134217728n,
    67108864n,
    33554432n,
    16777216n,
    8388608n,
    4194304n,
    2097152n,
    1048576n,
    524288n,
    262144n,
    131072n,
    65536n,
    32768n,
    16384n,
    8192n,
    4096n,
    2048n,
    1024n,
    512n,
    256n,
    128n,
    64n,
    32n,
    16n,
    8n,
    4n,
    2n,
    1n,
]) // Array.from({ length: 32 }, (_, i) => 1n << BigInt(31 - i))
