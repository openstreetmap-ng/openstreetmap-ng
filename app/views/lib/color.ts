import { memoize } from "@std/cache/memoize"
import { decodeHex, encodeHex } from "@std/encoding/hex"

const HEX_TRIPLET_RE = /^(.)(.)(.)$/

export const darkenColor = memoize((hex: string, amount: number) => {
    const rrggbb = hex.slice(1).replace(HEX_TRIPLET_RE, "$1$1$2$2$3$3")
    const rgb = decodeHex(rrggbb)
    const m = 1 - amount
    for (let i = 0; i < 3; i++) rgb[i] = Math.round(rgb[i] * m)
    return `#${encodeHex(rgb)}`
})
