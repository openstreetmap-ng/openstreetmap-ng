import { getLocaleOptions } from "@lib/locale"
import { mount } from "@lib/mount"
import { type APIDetail, configureStandardForm } from "@lib/standard-form"
import i18next from "i18next"

mount("settings-body", (body) => {
    const settingsForm = body.querySelector("form.settings-form")!
    const displayNameInput = settingsForm.querySelector("input[name=display_name]")!
    const displayNameBlacklist = displayNameInput.dataset.blacklist!
    const languageSelect = settingsForm.querySelector('select[name="language"]')!

    const fragment = document.createDocumentFragment()
    for (const locale of getLocaleOptions()) {
        const option = document.createElement("option")
        option.value = locale.code
        option.textContent = locale.flag
            ? `${locale.flag} ${locale.displayName}`
            : locale.displayName
        fragment.append(option)
    }
    languageSelect.append(fragment)
    languageSelect.value = languageSelect.getAttribute("value")!

    configureStandardForm(
        settingsForm,
        () => {
            // On success callback, reload the page
            console.debug("onSettingsFormSuccess")
            window.location.reload()
        },
        {
            validationCallback: () => {
                const result: APIDetail[] = []

                const displayNameChars = new Set(displayNameInput.value)
                if (
                    displayNameBlacklist.split("").some((c) => displayNameChars.has(c))
                ) {
                    const msg = i18next.t("validations.url_characters", {
                        characters: displayNameBlacklist,
                        interpolation: { escapeValue: false },
                    })
                    result.push({ type: "error", loc: ["", "display_name"], msg })
                }

                return result
            },
        },
    )
})
