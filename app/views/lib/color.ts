import { memoize } from "@std/cache/memoize"

export const darkenColor = memoize((hex: string, amount: number) => {
    const hexCode = hex.replace("#", "")

    let r: string
    let g: string
    let b: string
    if (hexCode.length === 3) {
        r = hexCode[0].repeat(2)
        g = hexCode[1].repeat(2)
        b = hexCode[2].repeat(2)
    } else if (hexCode.length === 6) {
        r = hexCode.slice(0, 2)
        g = hexCode.slice(2, 4)
        b = hexCode.slice(4, 6)
    } else {
        console.error("Invalid hex color", hex)
        return hex
    }

    const darken = (value: string) =>
        Math.round(Number.parseInt(value, 16) * (1 - amount))
            .toString(16)
            .padStart(2, "0")

    return `#${darken(r)}${darken(g)}${darken(b)}`
})
