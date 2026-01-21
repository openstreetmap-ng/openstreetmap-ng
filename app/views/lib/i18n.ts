import { primaryLanguage } from "@lib/config"
import { mapEntries } from "@std/collections/map-entries"
import { init, type Resource, t } from "i18next"
import type { ComponentChild } from "preact"

const resources: Resource = (window as any).locales
console.debug("I18n: Discovered locales", Object.keys(resources))

init({
  lng: primaryLanguage,
  fallbackLng: primaryLanguage === "en" ? false : "en",
  contextSeparator: "__",
  resources: resources,
})

const SPLIT_TOKEN = "__I18N_RICH_"

type RichReplacement = ComponentChild | (() => ComponentChild)

const isRichReplacement = (value: unknown): value is RichReplacement => {
  if (typeof value === "function") return true
  if (Array.isArray(value)) return true
  if (value === null || typeof value !== "object") return false
  return "type" in value && "props" in value
}

const interleaveTokens = (
  content: string,
  replacements: Map<string, RichReplacement>,
) => {
  const tokens = Array.from(replacements.keys())
  if (!tokens.length) return content

  const result: ComponentChild[] = []
  let remaining = content

  while (remaining) {
    let nextToken: string | null = null
    let nextIndex = -1

    for (const token of tokens) {
      const index = remaining.indexOf(token)
      if (index < 0) continue
      if (nextIndex < 0 || index < nextIndex) {
        nextIndex = index
        nextToken = token
      }
    }

    if (nextToken === null) {
      result.push(remaining)
      break
    }

    if (nextIndex > 0) result.push(remaining.slice(0, nextIndex))

    const replacement = replacements.get(nextToken)
    if (typeof replacement === "function") {
      result.push(replacement())
    } else if (replacement !== undefined) {
      result.push(replacement)
    } else {
      result.push(nextToken)
    }

    remaining = remaining.slice(nextIndex + nextToken.length)
  }

  return result.length === 1 ? result[0] : result
}

export const tRich = (key: string, options?: Record<string, unknown>) => {
  if (!options) return t(key)

  const replacements = new Map<string, RichReplacement>()
  let tokenIndex = 0

  const tokenized = mapEntries(options, ([name, value]) => {
    if (!isRichReplacement(value)) return [name, value]
    const token = `${SPLIT_TOKEN}${tokenIndex++}__`
    replacements.set(token, value)
    return [name, token]
  })

  const translated = t(key, tokenized as any)
  const content = typeof translated === "string" ? translated : String(translated)
  return interleaveTokens(content, replacements)
}
