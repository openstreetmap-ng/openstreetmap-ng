import i18next from "i18next"
import { primaryLanguage } from "./_config.js"

const resources = window.locales
console.debug("Discovered i18next locales", Object.keys(resources))

i18next.init({
    lng: primaryLanguage,
    fallbackLng: primaryLanguage === 'en' ? false : 'en',
    contextSeparator: "__",
    resources: resources,
})
