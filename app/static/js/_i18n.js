import i18next from "i18next"
import HttpApi from "i18next-http-backend"
import { languages, localeHashMap, primaryLanguage } from "./_config.js"

i18next.use(HttpApi).init({
    lng: primaryLanguage,
    fallbackLng: languages.slice(-1)[0],
    supportedLngs: languages,
    backend: {
        loadPath: (lngs, namespaces) => {
            const [locale] = lngs
            const hash = localeHashMap[locale]
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
