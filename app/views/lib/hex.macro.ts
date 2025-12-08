/** Build-time macro: generate byte-to-hex lookup table (256 entries) */
export function getB2HLut() {
    return Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, "0"))
}

/** Build-time macro: generate hex-to-byte lookup table (128 entries) */
export function getH2BLut() {
    // ASCII '0'-'9' (48-57), 'A'-'F' (65-70), 'a'-'f' (97-102)
    const lut = new Array<number>(128).fill(0)
    for (let i = 0; i < 10; i++) lut[48 + i] = i
    for (let i = 0; i < 6; i++) lut[65 + i] = 10 + i
    for (let i = 0; i < 6; i++) lut[97 + i] = 10 + i
    return lut
}
