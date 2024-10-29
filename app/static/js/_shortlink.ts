import { mod } from "./_utils"
import type { LonLatZoom } from "./leaflet/_map-utils"

/** 64 chars to encode 6 bits */
const _ARRAY = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_~"

/**
 * Encode a coordinate and zoom level to a short link code
 * @example
 * shortLinkEncode(5.123, 10.456, 17)
 * // => "wF7ZdNbjU-"
 */
export const shortLinkEncode = ({ lon, lat, zoom }: LonLatZoom): string => {
    const x = BigInt(Math.floor(mod(lon + 180, 360) * 11930464.711111112)) // (2 ** 32) / 360
    const y = BigInt(Math.floor((lat + 90) * 23860929.422222223)) // (2 ** 32) / 180
    let c = 0n

    for (let i = 31n; i >= 0; i--) {
        c = (c << 2n) | (((x >> i) & 1n) << 1n) | ((y >> i) & 1n)
    }

    const d = Math.ceil((zoom + 8) / 3)
    const r = (zoom + 8) % 3

    const strList = new Array(d + r)
    if (r) strList.fill("-", d)

    for (let i = 0; i < d; i++) {
        const digit = (c >> (58n - 6n * BigInt(i))) & 0x3fn
        strList[i] = _ARRAY[Number(digit)]
    }

    return strList.join("")
}
