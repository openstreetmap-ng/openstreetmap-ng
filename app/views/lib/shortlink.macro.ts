// TODO: return bigint[] when supported https://github.com/unplugin/unplugin-macros/issues/121
/** Build-time macro: generate bit masks for coordinate interleaving (Morton code / Z-order curve) */
export function getBitMasks() {
    return Array.from({ length: 32 }, (_, i) => (1n << BigInt(31 - i)).toString())
}
