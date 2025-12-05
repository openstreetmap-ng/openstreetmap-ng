import { memoize } from "@lib/memoize"
import { config } from "./config"

export type LocaleOption = {
    code: string
    nativeName: string
    englishName: string
    displayName: string
    flag?: string
}

export const getLocaleOptions = memoize((): readonly LocaleOption[] =>
    config.locales.map((locale) => {
        const nativeName = locale.nativeName
        const englishName = locale.englishName ?? nativeName
        const displayName = locale.englishName
            ? `${nativeName} (${englishName})`
            : nativeName

        const option: LocaleOption = {
            code: locale.code,
            nativeName,
            englishName,
            displayName,
            flag: locale.flag,
        }
        return option
    }),
)
