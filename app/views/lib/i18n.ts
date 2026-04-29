import { primaryLanguage } from "@lib/config"
import { mapEntries } from "@std/collections/map-entries"
import { init, type Resource, t } from "i18next"
import type { ComponentChild } from "preact"
import { isValidElement } from "preact/compat"

const resources: Resource = (window as any).locales
console.debug("I18n: Discovered locales", Object.keys(resources))

void init({
  initAsync: false,
  lng: primaryLanguage,
  fallbackLng: primaryLanguage === "en" ? false : "en",
  contextSeparator: "__",
  showSupportNotice: false,
  resources: resources,
})

const interleaveTokens = (
  content: string,
  replacements: Map<string, ComponentChild>,
) => {
  const tokens = [...replacements.keys()]
  if (!tokens.length) return content

  const result: ComponentChild[] = []
  let remaining = content

  while (remaining) {
    let nextToken: string | null = null
    let nextIndex = -1

    for (const token of tokens) {
      const index = remaining.indexOf(token)
      if (index === -1) continue
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
    if (replacement !== undefined) {
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

  const replacements = new Map<string, ComponentChild>()
  let tokenIndex = 0

  const tokenized = mapEntries(options, ([name, value]) => {
    if (!isValidElement(value)) return [name, value]
    const token = `\x1FI18N_RICH_${tokenIndex++}\x1F`
    replacements.set(token, value as ComponentChild)
    return [name, token]
  })

  const translated = t(key, tokenized)
  // oxlint-disable-next-line typescript/no-base-to-string
  const content = typeof translated === "string" ? translated : String(translated)
  return interleaveTokens(content, replacements)
}
