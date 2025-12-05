import { memoize } from "@lib/memoize"

const getB2HLut = memoize(() =>
    Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, "0")),
)

export const toHex = (bytes: Uint8Array) => {
    const lut = getB2HLut()
    let result = ""
    for (const byte of bytes) result += lut[byte]
    return result
}

// Hex-to-byte LUT: ASCII '0'-'9' (48-57), 'A'-'F' (65-70), 'a'-'f' (97-102)
const getH2BLut = memoize(() => {
    const lut = new Uint8Array(128)
    for (let i = 0; i < 10; i++) lut[48 + i] = i
    for (let i = 0; i < 6; i++) lut[65 + i] = 10 + i
    for (let i = 0; i < 6; i++) lut[97 + i] = 10 + i
    return lut
})

export const fromHex = (hex: string) => {
    const lut = getH2BLut()
    const len = hex.length >> 1
    const result = new Uint8Array(len)
    for (let i = 0; i < len; i++) {
        const j = i << 1
        result[i] = (lut[hex.charCodeAt(j)] << 4) | lut[hex.charCodeAt(j + 1)]
    }
    return result
}
