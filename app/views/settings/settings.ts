import { URLSAFE_BLACKLIST, URLSAFE_BLACKLIST_RE } from "@lib/config"
import { getLocaleDisplayName, LOCALE_OPTIONS } from "@lib/locale"
import { mount } from "@lib/mount"
import { type APIDetail, configureStandardForm } from "@lib/standard-form"
import { t } from "i18next"

mount("settings-body", (body) => {
    const settingsForm = body.querySelector("form.settings-form")!
    const displayNameInput = settingsForm.querySelector("input[name=display_name]")!
    const languageSelect = settingsForm.querySelector('select[name="language"]')!

    const fragment = document.createDocumentFragment()
    for (const locale of LOCALE_OPTIONS) {
        const option = document.createElement("option")
        option.value = locale[0]
        option.textContent = getLocaleDisplayName(locale, true)
        fragment.append(option)
    }
    languageSelect.append(fragment)
    languageSelect.value = languageSelect.getAttribute("value")!

    configureStandardForm(
        settingsForm,
        () => {
            // On success callback, reload the page
            console.debug("Settings: Saved")
            window.location.reload()
        },
        {
            validationCallback: () => {
                const result: APIDetail[] = []

                if (URLSAFE_BLACKLIST_RE.test(displayNameInput.value)) {
                    const msg = t("validations.url_characters", {
                        characters: URLSAFE_BLACKLIST,
                        interpolation: { escapeValue: false },
                    })
                    result.push({ type: "error", loc: ["", "display_name"], msg })
                }

                return result
            },
        },
    )
})
