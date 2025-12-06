import { config } from "@lib/config"
import { memoize } from "@lib/memoize"

export type LocaleOption = {
    code: string
    nativeName: string
    englishName: string
    displayName: string
    flag: string | null
}

export const getLocaleOptions = memoize(() =>
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
            flag: locale.flag ?? null,
        }
        return option
    }),
)
