import { getLocaleOptions } from "./locale.macro" with { type: "macro" }
import type { LocaleOption } from "./locale.macro"

export const LOCALE_OPTIONS = getLocaleOptions()

/** Get display name for a locale option, optionally prefixed with flag emoji */
export function getLocaleDisplayName(locale: LocaleOption, withFlag = false): string {
  const [, english, native, flag] = locale
  const displayName = native ? `${native} (${english})` : english
  return withFlag && flag ? `${flag} ${displayName}` : displayName
}
