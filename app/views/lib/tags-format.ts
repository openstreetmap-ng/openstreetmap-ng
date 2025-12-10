import { memoize } from "@std/cache/memoize"
import { primaryLanguage } from "./config"
import { getWikiData } from "./tags-format.macro" with { type: "macro" }

const { localeSets, wikiPages: WIKI_PAGES } = getWikiData()

const getLocaleSet = memoize((index: number) => new Set(localeSets[index]))

// Wiki locale prefix: "zh-hans" -> "Zh-Hans:"
const localeWikiPrefix = (locale: string) =>
    `${locale
        .split("-")
        .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
        .join("-")}:`

// Use "" for English
const USER_LOCALES =
    primaryLanguage === "en"
        ? [{ code: "", prefix: "" }]
        : [
              { code: primaryLanguage, prefix: localeWikiPrefix(primaryLanguage) },
              { code: "", prefix: "" },
          ]

const URL_RE = /^https?:\/\//i
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const WIKI_ID_RE = /^[Qq][1-9]\d*$/
const WIKI_LANG_RE = /^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?$/
const WIKI_LANG_VALUE_RE = /^([a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?):(.+)$/
const WIKIMEDIA_ENTRY_RE = /^(?:file|category):/i
const MAX_VALUE_PARTS = 10

// ============================================================
// Validation
// ============================================================

const isUrlString = (s: string) => URL_RE.test(s)

const isEmailString = (s: string) => s.length <= 254 && EMAIL_RE.test(s)

const isColorValid = (s: string) => CSS.supports("color", s)

const isWikiId = (s: string) => s.length >= 2 && WIKI_ID_RE.test(s)

const isWikimediaEntry = (s: string) => WIKIMEDIA_ENTRY_RE.test(s)

// ============================================================
// Wiki Links
// ============================================================

const getWikiUrl = (key: string, value: string | null) => {
    const localeSetIndex = WIKI_PAGES[key]?.[value ?? "*"]
    if (localeSetIndex === undefined) return null

    const availableLocales = getLocaleSet(localeSetIndex)
    for (const { code, prefix } of USER_LOCALES) {
        if (availableLocales.has(code)) {
            const page =
                value !== null
                    ? `Tag:${encodeURIComponent(key)}=${encodeURIComponent(value)}`
                    : `Key:${encodeURIComponent(key)}`
            return `https://wiki.openstreetmap.org/wiki/${prefix}${page}`
        }
    }
    return null
}

// ============================================================
// Value Rendering
// ============================================================

const createLink = (text: string, href: string, safe = false) => {
    const a = document.createElement("a")
    a.className = "tag-value"
    a.href = href
    a.rel = safe ? "noopener" : "noopener nofollow"
    a.textContent = text
    return a
}

const createSpan = (text: string) => {
    const span = document.createElement("span")
    span.className = "tag-value"
    span.textContent = text
    return span
}

const createColorSpan = (text: string, color: string) => {
    const span = document.createElement("span")
    span.className = "tag-value"
    const preview = document.createElement("span")
    preview.className = "color-preview"
    preview.style.background = color
    span.appendChild(preview)
    span.appendChild(document.createTextNode(text))
    return span
}

// ============================================================
// Formatters (ordered by cost: cheap first)
// ============================================================

type FormatterFn = (keyParts: string[], text: string) => HTMLElement | null

const formatUrl: FormatterFn = (_, text) =>
    isUrlString(text) ? createLink(text, text) : null

const formatColor: FormatterFn = (_, text) =>
    isColorValid(text) ? createColorSpan(text, text) : null

const formatEmail: FormatterFn = (_, text) =>
    isEmailString(text) ? createLink(text, `mailto:${text}`) : null

const formatPhone: FormatterFn = (_, text) => {
    const span = createSpan(text)
    ;(async () => {
        const { parsePhoneNumberFromString } = await import("libphonenumber-js/min")
        const phone = parsePhoneNumberFromString(text)
        if (phone?.isValid()) span.replaceWith(createLink(text, phone.getURI()))
    })()
    return span
}

const formatWikidata: FormatterFn = (_, text) =>
    isWikiId(text)
        ? createLink(text, `https://www.wikidata.org/entity/${text}`, true)
        : null

const formatWikimediaCommons: FormatterFn = (_, text) =>
    isWikimediaEntry(text)
        ? createLink(
              text,
              `https://commons.wikimedia.org/wiki/${encodeURIComponent(text)}`,
              true,
          )
        : null

const formatWikipedia: FormatterFn = (keyParts, text) => {
    let lang = "en"
    for (const part of keyParts) {
        if (WIKI_LANG_RE.test(part)) {
            lang = part
            break
        }
    }

    let title = text
    const match = WIKI_LANG_VALUE_RE.exec(text)
    if (match) {
        lang = match[1]
        title = match[2]
    }

    return createLink(
        text,
        `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title)}`,
        true,
    )
}

const FORMATTER_MAP: Record<string, FormatterFn[]> = {
    colour: [formatColor],
    email: [formatEmail],
    phone: [formatPhone],
    fax: [formatPhone],
    host: [formatUrl],
    website: [formatUrl],
    url: [formatUrl],
    source: [formatUrl],
    image: [formatUrl],
    wikidata: [formatWikidata],
    wikimedia_commons: [formatWikimediaCommons],
    wikipedia: [formatUrl, formatWikipedia],
}

// ============================================================
// Renderers
// ============================================================

const renderValue = (key: string, keyParts: string[], text: string) => {
    // Try formatters based on key parts
    for (const keyPart of keyParts) {
        const formatters = FORMATTER_MAP[keyPart]
        if (formatters) {
            for (const formatter of formatters) {
                const result = formatter(keyParts, text)
                if (result) return result
            }
        }
    }

    // Try wiki link for value
    const wikiUrl = getWikiUrl(key, text)
    if (wikiUrl) return createLink(text, wikiUrl, true)

    // Plain text
    return createSpan(text)
}

const renderKey = (key: string) => {
    const wikiUrl = getWikiUrl(key, null)
    return wikiUrl ? createLink(key, wikiUrl, true) : createSpan(key)
}

const renderValueList = (
    key: string,
    keyParts: string[],
    value: string,
    className: string,
) => {
    const div = document.createElement("div")
    div.className = className
    for (const rawPart of value.split(";").slice(0, MAX_VALUE_PARTS)) {
        const part = rawPart.trim()
        if (part) div.appendChild(renderValue(key, keyParts, part))
    }
    return div
}

const renderValues = (key: string, value: string) =>
    renderValueList(key, key.split(":"), value, "tag-values")

const enhanceRow = (row: HTMLTableRowElement, key: string, value: string) => {
    row.cells[0].replaceChildren(renderKey(key))
    row.cells[1].replaceChildren(renderValues(key, value))
}

const createRow = (key: string, value: string, status?: string) => {
    const row = document.createElement("tr")
    if (status) row.dataset.status = status
    row.appendChild(document.createElement("td"))
    row.appendChild(document.createElement("td"))
    enhanceRow(row, key, value)
    return row
}

/**
 * Enhance a tags table container.
 * Server renders basic HTML structure, this adds links/formatting.
 * Optional data-tags-old for diff mode.
 */
export const configureTagsFormat = (container: HTMLElement | null) => {
    if (!container) return

    const tbody = container.querySelector("tbody")!

    // Parse old tags for diff (if present)
    const oldTagsJson = container.dataset.tagsOld
    const oldTags: Record<string, string> | null = oldTagsJson
        ? JSON.parse(oldTagsJson)
        : null
    container.removeAttribute("data-tags-old")

    // Build current tags map from existing rows
    const currentTags = new Map<string, { row: HTMLTableRowElement; value: string }>()
    for (const row of tbody.querySelectorAll("tr")) {
        const key = row.cells[0].textContent.trim()
        const value = row.cells[1].textContent.trim()
        currentTags.set(key, { row, value })
    }

    // Enhance existing rows + compute diff status
    for (const [key, { row, value }] of currentTags) {
        // Cache oldValue to avoid double lookup
        const oldValue = oldTags?.[key]
        if (oldTags) {
            if (oldValue === undefined) {
                row.dataset.status = "added"
            } else if (oldValue !== value) {
                row.dataset.status = "modified"
            }
        }
        enhanceRow(row, key, value)

        // Add previous values for modified tags
        if (oldValue !== undefined && oldValue !== value) {
            row.cells[1].appendChild(
                renderValueList(key, key.split(":"), oldValue, "tag-previous"),
            )
        }
    }

    // Add deleted rows (in old but not current)
    if (oldTags) {
        const deletedRows: HTMLTableRowElement[] = []
        for (const [key, value] of Object.entries(oldTags)) {
            if (!currentTags.has(key)) {
                deletedRows.push(createRow(key, value, "deleted"))
            }
        }

        // Insert deleted rows in sorted position
        if (deletedRows.length) {
            const rowsWithKeys = [...tbody.querySelectorAll("tr"), ...deletedRows]
                .map((row) => ({ row, key: row.cells[0].textContent }))
                .sort((a, b) => a.key.localeCompare(b.key))
            const fragment = document.createDocumentFragment()
            for (const { row } of rowsWithKeys) fragment.appendChild(row)
            tbody.replaceChildren(fragment)
        }
    }

    console.debug("Formatted", currentTags.size, "tags")
}
