import { readFileSync } from "node:fs"
import { distinct } from "@std/collections/distinct"
import { mapNotNullish } from "@std/collections/map-not-nullish"
import { sortBy } from "@std/collections/sort-by"

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

// Filter and normalize locale array: lowercase, dedupe, sort
const normalizeLocales = (locales: string[]) =>
  sortBy(
    distinct(
      locales
        .map((l) => l.toLowerCase())
        .filter(installedLocales.has, installedLocales),
    ),
    (l) => l,
  )

// Pass 1: Count frequency of each locale set
const localeSetFreq = new Map<string, { locales: string[]; count: number }>()

for (const values of Object.values(wikiPagesRaw)) {
  for (const locales of Object.values(values)) {
    const filtered = normalizeLocales(locales)
    if (!filtered.length) continue
    const key = filtered.join(",")
    const entry = localeSetFreq.get(key)
    if (entry) entry.count++
    else localeSetFreq.set(key, { locales: filtered, count: 1 })
  }
}

// Sort by frequency (most common = index 0) for better compression
const sortedLocaleSets = sortBy(localeSetFreq.entries(), ([, { count }]) => count, {
  order: "desc",
})
const localeSets = sortedLocaleSets.map(([_, { locales }]) => locales)
const localeSetIndex = new Map(sortedLocaleSets.map(([key], i) => [key, i]))

// Pass 2: Build wiki pages with frequency-sorted indices
const wikiPages: Record<string, Record<string, number>> = {}

for (const [key, values] of Object.entries(wikiPagesRaw)) {
  const keyValues = Object.fromEntries(
    mapNotNullish(Object.entries(values), ([value, locales]) => {
      const normalized = normalizeLocales(locales)
      if (!normalized.length) return null
      return [value, localeSetIndex.get(normalized.join(","))!] as const
    }),
  )
  if (Object.keys(keyValues).length) wikiPages[key] = keyValues
}

export const getWikiData = () => ({
  localeSets,
  wikiPages,
})
