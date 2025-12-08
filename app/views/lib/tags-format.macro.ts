import { readFileSync } from "node:fs"

const wikiPagesRaw: Record<string, Record<string, string[]>> = JSON.parse(
    readFileSync("config/wiki_pages.json", "utf8"),
)

const i18nextMap: Record<string, string> = JSON.parse(
    readFileSync("config/locale/i18next/map.json", "utf8"),
)

// Build set of installed locales (lowercase for matching)
// Include "" for English (wiki JSON uses "" for default/English)
const installedLocales = new Set(Object.keys(i18nextMap))
installedLocales.delete("en")
installedLocales.add("")

// Deduplicate locale sets
const localeSetMap = new Map<string, number>()
const localeSets: string[][] = []

const getLocaleSetIndex = (locales: string[]): number => {
    // Filter to installed locales only, lowercase, and dedupe
    const filtered = [
        ...new Set(
            locales.map((l) => l.toLowerCase()).filter((l) => installedLocales.has(l)),
        ),
    ]
    const key = filtered.join(",")

    let index = localeSetMap.get(key)
    if (index === undefined) {
        index = localeSets.length
        localeSets.push(filtered)
        localeSetMap.set(key, index)
    }
    return index
}

// Build optimized wiki pages structure
// { "key:value": localeSetIndex } where value "*" is wildcard
const wikiPages: Record<string, number> = {}

for (const [keyPart, values] of Object.entries(wikiPagesRaw)) {
    for (const [value, locales] of Object.entries(values)) {
        const index = getLocaleSetIndex(locales)
        // Skip entries with no installed locales
        if (localeSets[index].length === 0) continue
        wikiPages[`${keyPart}:${value}`] = index
    }
}

export const getWikiData = () => ({
    localeSets,
    wikiPages,
})
