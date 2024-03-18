import i18next from "i18next"
import { activityTracking } from "../_config.js"
import { configureStandardForm } from "../_standard-form.js"

const signupBody = document.querySelector("body.signup-body")
if (signupBody) {
    const signupForm = signupBody.querySelector("form.signup-form")
    const trackingInput = signupForm.querySelector("[name=tracking]")
    const displayNameInput = signupForm.querySelector("[name=display_name]")
    const emailInput = signupForm.querySelector("[name=email]")
    const emailConfirmationInput = signupForm.querySelector("[name=email_confirm]")
    const passwordInput = signupForm.querySelector("[name=password]")
    const passwordConfirmationInput = signupForm.querySelector("[name=password_confirm]")

    trackingInput.value = activityTracking

    const onSignupSuccess = () => {
        location.href = "/user/terms"
    }

    const onClientValidation = () => {
        const result = new Array()

        // TODO: better way to do it?
        if (!/^[^\/;.,?%#]+$/.test(displayNameInput.value)) {
            const msg = i18next.t("validations.url_characters", {
                characters: "/;.,?%#",
                interpolation: { escapeValue: false },
            })
            result.push({ type: "error", loc: ["", "display_name"], msg })
        }

        if (emailInput.value !== emailConfirmationInput.value) {
            const msg = i18next.t("validation.email_missmatch")
            result.push({ type: "error", loc: ["", "email"], msg })
            result.push({ type: "error", loc: ["", "email_confirm"], msg })
        }

        if (passwordInput.value !== passwordConfirmationInput.value) {
            const msg = i18next.t("validation.password_missmatch")
            result.push({ type: "error", loc: ["", "password"], msg })
            result.push({ type: "error", loc: ["", "password_confirm"], msg })
        }

        return result
    }

    configureStandardForm(signupForm, onSignupSuccess, onClientValidation)
}
