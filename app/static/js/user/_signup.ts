import i18next from "i18next"
import { activityTracking } from "../_config"
import { type APIDetail, configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.signup-body")
if (body) {
    const signupForm = body.querySelector("form.signup-form")
    const displayNameInput = signupForm.elements.namedItem("display_name") as HTMLInputElement
    const displayNameBlacklist = displayNameInput.dataset.blacklist
    const passwordInput = signupForm.elements.namedItem("password") as HTMLInputElement
    const passwordConfirmationInput = signupForm.elements.namedItem("password_confirm") as HTMLInputElement

    const trackingInput = signupForm.elements.namedItem("tracking") as HTMLInputElement
    trackingInput.value = activityTracking.toString()

    configureStandardForm(
        signupForm,
        () => {
            console.debug("onSignupFormSuccess")
            window.location.href = "/user/terms"
        },
        () => {
            const result: APIDetail[] = []

            // Validate name for blacklisted characters
            const displayNameValue = displayNameInput.value
            if (displayNameBlacklist.split("").some((c) => displayNameValue.includes(c))) {
                const msg = i18next.t("validations.url_characters", {
                    characters: displayNameBlacklist,
                    interpolation: { escapeValue: false },
                })
                result.push({ type: "error", loc: ["", "display_name"], msg })
            }

            // Validate passwords equality
            if (passwordInput.value !== passwordConfirmationInput.value) {
                const msg = i18next.t("validation.passwords_missmatch")
                result.push({ type: "error", loc: ["", "password"], msg })
                result.push({ type: "error", loc: ["", "password_confirm"], msg })
            }

            return result
        },
    )
}
