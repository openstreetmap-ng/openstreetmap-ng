import i18next from "i18next"
import { configureStandardForm } from "../_standard-form.js"
import { isHrefCurrentPage } from "../_utils.js"

// Add active class to current nav-lik
const navLinks = document.querySelectorAll(".settings-nav .nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}

const settingsBody = document.querySelector("body.settings-body")
if (settingsBody) {
    const settingsForm = settingsBody.querySelector("form.settings-form")
    const displayNameInput = settingsForm.elements.display_name
    const displayNameBlacklist = displayNameInput.dataset.blacklist

    const onSettingsFormSuccess = () => {
        location.reload()
    }

    const onSettingsClientValidation = () => {
        const result = new Array()

        const displayNameValue = displayNameInput.value
        if (displayNameBlacklist.split("").some((c) => displayNameValue.includes(c))) {
            const msg = i18next.t("validations.url_characters", {
                characters: displayNameBlacklist,
                interpolation: { escapeValue: false },
            })
            result.push({ type: "error", loc: ["", "display_name"], msg })
        }

        return result
    }

    configureStandardForm(settingsForm, onSettingsFormSuccess, onSettingsClientValidation)
}
