/** Build-time macro: generate bit masks for coordinate interleaving (Morton code / Z-order curve) */
export const getBitMasks = () =>
  Array.from({ length: 32 }, (_, i) => 1n << BigInt(31 - i))
