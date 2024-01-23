import i18next from "i18next"
import HttpApi from "i18next-http-backend"
import { languages, localeVersion, primaryLanguage } from "./_params.js"

i18next.use(HttpApi).init({
    lng: primaryLanguage,
    fallbackLng: languages.slice(-1)[0], // last language is always the default language
    supportedLngs: languages,
    backend: {
        // TODO: hash per locale file
        loadPath: `/static-locale/${localeVersion}/{{lng}}.json`,
        requestOptions: {
            mode: "no-cors",
            credentials: "omit",
            priority: "high",
        },
    },
})
