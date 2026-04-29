import { memoize } from "@std/cache/memoize"
import type { LocaleOption } from "./locale.macro"
import { getLocaleOptions } from "./locale.macro" with { type: "macro" }

export const LOCALE_OPTIONS = getLocaleOptions()

/** Get display name for a locale option, optionally prefixed with flag emoji */
export const getLocaleDisplayName = (locale: LocaleOption, withFlag = false) => {
  const [, english, native, flag] = locale
  const displayName = native ? `${native} (${english})` : english
  return withFlag && flag ? `${flag} ${displayName}` : displayName
}

const getLocaleOptionByCode = memoize(
  () => new Map(LOCALE_OPTIONS.map((locale) => [locale[0], locale] as const)),
)
export const getLocaleDisplayNameByCode = (code: string, withFlag = false) => {
  const locale = getLocaleOptionByCode().get(code)
  return locale ? getLocaleDisplayName(locale, withFlag) : code
}
