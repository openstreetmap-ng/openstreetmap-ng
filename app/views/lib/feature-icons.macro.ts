import { readFileSync } from "node:fs"
import { parse as parseToml } from "@std/toml"

const iconsRaw = parseToml(readFileSync("config/feature_icons.toml", "utf8")) as Record<
    string,
    Record<string, string>
>

const popularityRaw: Record<string, Record<string, number>> = JSON.parse(
    readFileSync("config/feature_icons_popular.json", "utf8"),
)

// Pass 1: Collect all unique filenames and assign indices
const fileSet = new Set<string>()
for (const values of Object.values(iconsRaw)) {
    for (const filename of Object.values(values)) {
        fileSet.add(filename)
    }
}
// Sort for deterministic output and better compression
const files = [...fileSet].sort()
const fileIndex = new Map(files.map((f, i) => [f, i]))

// Pass 2: Collect all (configKey, value) pairs with popularity for ranking
type IconEntry = { configKey: string; value: string; popularity: number }
const allEntries: IconEntry[] = []

for (const [configKey, values] of Object.entries(iconsRaw)) {
    for (const value of Object.keys(values)) {
        const popularity = popularityRaw[configKey]?.[value] ?? 0
        allEntries.push({ configKey, value, popularity })
    }
}

// Sort by popularity ascending (lower = rarer = higher priority)
// This determines the relative priority rank
allEntries.sort((a, b) => a.popularity - b.popularity)

// Assign priority ranks (0 = highest priority, picked first in ties)
const priorityMap = new Map<string, number>()
for (let i = 0; i < allEntries.length; i++) {
    const { configKey, value } = allEntries[i]
    priorityMap.set(`${configKey}\0${value}`, i)
}

// Pass 3: Build optimized icons map (configKey -> value -> fileIndex)
const icons: Record<string, Record<string, number>> = {}
for (const [configKey, values] of Object.entries(iconsRaw)) {
    icons[configKey] = {}
    for (const [value, filename] of Object.entries(values)) {
        icons[configKey][value] = fileIndex.get(filename)!
    }
}

// Pass 4: Build priority map (configKey -> value -> priority rank)
const priority: Record<string, Record<string, number>> = {}
for (const [configKey, values] of Object.entries(iconsRaw)) {
    priority[configKey] = {}
    for (const value of Object.keys(values)) {
        priority[configKey][value] = priorityMap.get(`${configKey}\0${value}`)!
    }
}

// Extract unique base keys (strip ".type" suffix) for fast intersection
const keys = [...new Set(Object.keys(iconsRaw).map((k) => k.split(".")[0]))].sort()

export const getFeatureIconsData = () => ({
    files,
    icons,
    priority,
    keys,
})
