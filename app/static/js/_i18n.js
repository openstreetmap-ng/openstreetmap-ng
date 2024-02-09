import i18next from "i18next"
import { languages, primaryLanguage } from "./_config.js"

const resources = window.locales
console.debug("Discovered i18next locales", Object.keys(resources))

i18next.init({
    lng: primaryLanguage,
    fallbackLng: languages.slice(-1)[0],
    supportedLngs: languages,
    contextSeparator: "__",
    resources: resources,
})
