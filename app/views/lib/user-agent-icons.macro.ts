import { existsSync, readdirSync } from "node:fs"
import { BROWSER_ALIASES_MAP, OS_MAP } from "bowser/src/constants.js"

// Semantic aliases only (where we want a different icon than the name suggests)
const OS_SEMANTIC_ALIASES: Record<string, string> = {
    macos: "apple",
    ios: "apple",
}

/** Build-time macro: generate browser display name to icon path mapping */
export function getBrowserIconMap() {
    const fsDir = "app/static/img/browser"
    const urlDir = "/static/img/browser"

    // Collect available icons: stem -> url path
    const available = new Map<string, string>()

    const fsGenerated = `${fsDir}/_generated`
    if (existsSync(fsGenerated)) {
        for (const file of readdirSync(fsGenerated)) {
            if (!file.endsWith(".webp")) continue
            available.set(file.slice(0, -5), `${urlDir}/_generated/${file}`)
        }
    }

    for (const file of readdirSync(fsDir)) {
        if (!file.endsWith(".png")) continue
        const stem = file.slice(0, -4)
        if (!available.has(stem)) {
            available.set(stem, `${urlDir}/${file}`)
        }
    }

    const map: Record<string, string> = {}

    // Map bowser display names to icon paths
    for (const [displayName, normalizedKey] of Object.entries(BROWSER_ALIASES_MAP)) {
        // Convert snake_case to kebab-case (browser-logos convention)
        const iconKey = normalizedKey.replace(/_/g, "-")
        const path = available.get(iconKey)
        if (path) map[displayName] = path
    }

    return map
}

/** Build-time macro: generate OS display name to icon path mapping */
export function getOsIconMap() {
    const bsIcons = new Set(
        readdirSync("node_modules/bootstrap-icons/icons")
            .filter((f) => f.endsWith(".svg"))
            .map((f) => f.slice(0, -4)),
    )
    const siIcons = new Set(
        readdirSync("node_modules/simple-icons/icons")
            .filter((f) => f.endsWith(".svg"))
            .map((f) => f.slice(0, -4)),
    )

    const map: Record<string, string> = {}

    // Map bowser OS display names to icon paths
    for (const displayName of Object.values(OS_MAP)) {
        const normalized = displayName.toLowerCase().replace(/\s+/g, "")
        const slug = OS_SEMANTIC_ALIASES[normalized] ?? normalized

        if (bsIcons.has(slug)) {
            map[displayName] = `/static-node_modules/bootstrap-icons/icons/${slug}.svg`
        } else if (siIcons.has(slug)) {
            map[displayName] = `/static-node_modules/simple-icons/icons/${slug}.svg`
        }
    }

    return map
}
