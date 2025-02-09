import i18next from "i18next"
import { type APIDetail, configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.settings-body")
if (body) {
    const settingsForm = body.querySelector("form.settings-form")
    const displayNameInput = settingsForm.elements.namedItem("display_name") as HTMLInputElement
    const displayNameBlacklist = displayNameInput.dataset.blacklist

    configureStandardForm(
        settingsForm,
        () => {
            // On success callback, reload the page
            console.debug("onSettingsFormSuccess")
            window.location.reload()
        },
        () => {
            const result: APIDetail[] = []

            const displayNameValue = displayNameInput.value
            if (displayNameBlacklist.split("").some((c) => displayNameValue.includes(c))) {
                const msg = i18next.t("validations.url_characters", {
                    characters: displayNameBlacklist,
                    interpolation: { escapeValue: false },
                })
                result.push({ type: "error", loc: ["", "display_name"], msg })
            }

            return result
        },
    )
}
