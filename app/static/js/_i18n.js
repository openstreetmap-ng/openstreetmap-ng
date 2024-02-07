import i18next from "i18next"
import HttpApi from "i18next-http-backend"
import { languages, primaryLanguage } from "./_config.js"
import { localeHashMap } from "./_locale_hash_map.js"

i18next.use(HttpApi).init({
    lng: primaryLanguage,
    fallbackLng: languages.slice(-1)[0],
    supportedLngs: languages,
    contextSeparator: "__",
    backend: {
        loadPath: (lngs, namespaces) => {
            const [locale] = lngs
            const hash = localeHashMap.get(locale)
            if (!hash) {
                console.error(`Missing locale hash for ${locale}`)
                return false
            }
            return `/static-locale/${locale}-${hash}.json`
        },
        requestOptions: {
            mode: "no-cors",
            credentials: "omit",
            priority: "high",
        },
    },
})
