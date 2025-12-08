import { getB2HLut, getH2BLut } from "./hex.macro" with { type: "macro" }

const B2H_LUT = getB2HLut()
const H2B_LUT = getH2BLut()

export const toHex = (bytes: Uint8Array) => {
    let result = ""
    for (const byte of bytes) result += B2H_LUT[byte]
    return result
}

export const fromHex = (hex: string) => {
    const len = hex.length >> 1
    const result = new Uint8Array(len)
    for (let i = 0; i < len; i++) {
        const j = i << 1
        result[i] = (H2B_LUT[hex.charCodeAt(j)] << 4) | H2B_LUT[hex.charCodeAt(j + 1)]
    }
    return result
}
