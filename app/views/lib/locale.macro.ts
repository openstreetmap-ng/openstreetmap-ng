import { readFileSync } from "node:fs"
import { mapNotNullish } from "@std/collections/map-not-nullish"
import { parse } from "@std/toml"

interface LocaleName {
    code: string
    english: string
    native: string | null
}

export type LocaleOption = readonly [
    code: string,
    english: string,
    native: string | null,
    flag?: string,
]

interface FlagsToml {
    passthrough: string[]
    [key: string]: string | string[]
}

/** Build regional indicator flag from 2-letter country code */
function toRegionalIndicator(code: string) {
    if (code.length !== 2) return null

    const upper = code.toUpperCase()

    // Special case: UN is not a country, don't show flag for Esperanto
    if (upper === "UN") return null

    const codepoints: number[] = []

    for (const char of upper) {
        const charCode = char.charCodeAt(0)
        // Only A-Z (65-90) are valid for regional indicators
        if (charCode < 65 || charCode > 90) return null

        const regional = 0x1f1a5 + charCode
        // Validate codepoint in regional indicator range (0x1F1E6-0x1F1FF)
        if (regional < 0x1f1e6 || regional > 0x1f1ff) return null

        codepoints.push(regional)
    }

    return String.fromCodePoint(...codepoints)
}

/** Build Unicode subdivision flag (e.g., GB-WLS -> Welsh flag) */
function toSubdivisionFlag(code: string) {
    // Format: XX-YYY (e.g., GB-WLS, GB-SCT)
    // Result: black flag + tag sequence + cancel tag
    const BLACK_FLAG = 0x1f3f4
    const TAG_BASE = 0xe0000
    const CANCEL_TAG = 0xe007f

    const codepoints = [BLACK_FLAG]

    // Add tag characters for the whole code (lowercase, no hyphen)
    const tagChars = code.toLowerCase().replace("-", "")
    for (const char of tagChars) {
        codepoints.push(TAG_BASE + char.charCodeAt(0))
    }

    codepoints.push(CANCEL_TAG)

    return String.fromCodePoint(...codepoints)
}

/** Compute flag emoji for a locale code */
function computeFlag(
    localeCode: string,
    flagLookup: Map<string, string>,
    passthroughSet: Set<string>,
) {
    const parts = localeCode.toUpperCase().split("-")

    // Try longest prefix first, then shorter (e.g., pt-PT tries PT-PT, then PT)
    for (let i = parts.length; i > 0; i--) {
        const code = parts.slice(0, i).join("-")
        const lowerCode = code.toLowerCase()

        // Check explicit mapping first
        let countryCode = flagLookup.get(lowerCode)

        // Check passthrough (locale code is country code)
        if (!countryCode && passthroughSet.has(lowerCode)) {
            countryCode = code
        }

        if (!countryCode) continue

        // Handle subdivision flags (e.g., GB-WLS, GB-SCT)
        if (countryCode.includes("-")) {
            return toSubdivisionFlag(countryCode)
        }

        // Compute regional indicator flag (returns null for invalid codes)
        const flag = toRegionalIndicator(countryCode)
        if (flag) return flag
    }

    return null
}

/** Build-time macro: generate locale options for language selector */
export function getLocaleOptions() {
    // Read data files
    const names: LocaleName[] = JSON.parse(
        readFileSync("config/locale/names.json", "utf-8"),
    )
    const flags = parse(readFileSync("config/locale/flags.toml", "utf-8")) as FlagsToml
    const installedLocales: Record<string, string> = JSON.parse(
        readFileSync("config/locale/i18next/map.json", "utf-8"),
    )

    // Build case-insensitive flag lookup (keys are uppercase in TOML)
    const flagLookup = new Map<string, string>()
    for (const [key, value] of Object.entries(flags)) {
        if (key === "passthrough") continue
        flagLookup.set(key.toLowerCase(), value as string)
    }

    // Add passthrough entries (locale code = country code)
    const passthroughSet = new Set(flags.passthrough.map((s) => s.toLowerCase()))

    // Filter to installed locales and build options
    const options = mapNotNullish(names, (name) => {
        if (!(name.code in installedLocales)) return null

        const native = name.native && name.native !== name.english ? name.native : null
        const flag = computeFlag(name.code, flagLookup, passthroughSet)

        return {
            tuple: flag
                ? ([name.code, name.english, native, flag] as const)
                : ([name.code, name.english, native] as const),
            sortKey: (native ?? name.english).toLowerCase(),
        }
    })

    // Sort by display name (case-insensitive)
    return options
        .sort((a, b) => a.sortKey.localeCompare(b.sortKey))
        .map((o) => o.tuple)
}
