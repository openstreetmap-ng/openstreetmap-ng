import { memoize } from "@lib/memoize"

const getB2HLut = memoize(() =>
    Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, "0")),
)

/** Convert a byte array to a hex string */
export const toHex = (bytes: Uint8Array) => {
    const lut = getB2HLut()
    let out = ""
    for (const byte of bytes) out += lut[byte]
    return out
}

const getH2BLut = memoize(() => {
    const lut = new Uint8Array(128)
    for (let i = 0; i < 10; i++) lut[48 + i] = i
    for (let i = 0; i < 6; i++) lut[65 + i] = 10 + i
    for (let i = 0; i < 6; i++) lut[97 + i] = 10 + i
    return lut
})

/** Convert a hex string to a byte array */
export const fromHex = (hex: string) => {
    const lut = getH2BLut()
    const len = hex.length >> 1
    const out = new Uint8Array(len)
    for (let i = 0; i < len; i++) {
        const j = i << 1
        out[i] = (lut[hex.charCodeAt(j)] << 4) | lut[hex.charCodeAt(j + 1)]
    }
    return out
}
