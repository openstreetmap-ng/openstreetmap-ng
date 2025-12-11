import { primaryLanguage } from "@lib/config"
import i18next, { type Resource } from "i18next"

const resources: Resource = (window as any).locales
console.debug("I18n: Discovered locales", Object.keys(resources))

i18next.init({
    lng: primaryLanguage,
    fallbackLng: primaryLanguage === "en" ? false : "en",
    contextSeparator: "__",
    resources: resources,
})
