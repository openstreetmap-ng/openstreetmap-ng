import i18next, { type Resource } from "i18next"
import { primaryLanguage } from "./_config"

const resources: Resource = (window as any).locales
console.debug("Discovered i18next locales", Object.keys(resources))

i18next.init({
    lng: primaryLanguage,
    fallbackLng: primaryLanguage === "en" ? false : "en",
    contextSeparator: "__",
    resources: resources,
})
