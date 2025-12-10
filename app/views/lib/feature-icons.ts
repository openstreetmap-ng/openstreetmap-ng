import { getFeatureIconsData } from "./feature-icons.macro" with { type: "macro" }

const {
    files: FILES,
    icons: ICONS,
    priority: PRIORITY,
    keys: _KEYS,
} = getFeatureIconsData()
const KEYS = new Set(_KEYS)

export type ElementType = "node" | "way" | "relation"

export interface FeatureIcon {
    filename: string
    title: string
}

/**
 * Get the feature icon for an element based on its tags and type.
 *
 * Algorithm mirrors Python feature_icon.py:
 * - Prefer value-specific over generic ("*")
 * - Prefer type-specific config (key.type) over generic (key)
 * - When multiple match, pick lowest priority (rarest tag)
 */
export const getFeatureIcon = (
    tags: Record<string, string> | null | undefined,
    elementType: ElementType,
): FeatureIcon | null => {
    if (!tags) return null

    // Find tag keys that exist in our config
    const matchedKeys: string[] = []
    for (const key of Object.keys(tags)) {
        if (KEYS.has(key)) matchedKeys.push(key)
    }
    if (!matchedKeys.length) return null

    // Collect matches: [priority, fileIndex, title]
    type Match = [number, number, string]

    // Try value-specific first, then generic ("*")
    for (const specific of [true, false]) {
        const results: Match[] = []

        for (const key of matchedKeys) {
            const value = specific ? tags[key] : "*"

            // Try type-specific config first (key.type), then generic (key)
            for (const configKey of [`${key}.${elementType}`, key]) {
                const valuesMap = ICONS[configKey]
                if (!valuesMap) continue

                const fileIdx = valuesMap[value]
                if (fileIdx === undefined) continue

                const prio = PRIORITY[configKey][value]
                const title = specific ? `${key}=${value}` : key
                results.push([prio, fileIdx, title])
            }
        }

        // Return match with lowest priority (rarest = most specific)
        if (results.length) {
            const best = results.reduce((a, b) => (a[0] < b[0] ? a : b))
            return { filename: FILES[best[1]], title: best[2] }
        }
    }

    return null
}

/**
 * Get feature icons for multiple elements.
 * Returns null for elements without a matching icon.
 */
export const getFeatureIcons = <
    T extends { tags: Record<string, string> | null; type: ElementType },
>(
    elements: (T | null)[],
): (FeatureIcon | null)[] =>
    elements.map((e) => (e ? getFeatureIcon(e.tags, e.type) : null))
