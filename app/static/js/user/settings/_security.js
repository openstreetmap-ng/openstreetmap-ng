import i18next from "i18next"
import { qsEncode } from "../../_qs.js"
import { configureStandardForm } from "../../_standard-form.js"

const settingsSecurityBody = document.querySelector("body.settings-security-body")
if (settingsSecurityBody) {
    const passwordForm = settingsSecurityBody.querySelector("form.password-form")
    const newPasswordInput = passwordForm.elements.new_password
    const newPasswordConfirmInput = passwordForm.elements.new_password_confirm
    const onPasswordFormSuccess = () => {
        passwordForm.reset()
    }
    const onPasswordValidation = () => {
        const result = new Array()
        if (newPasswordInput.value !== newPasswordConfirmInput.value) {
            const msg = i18next.t("validation.passwords_missmatch")
            result.push({ type: "error", loc: ["", "new_password"], msg })
            result.push({ type: "error", loc: ["", "new_password_confirm"], msg })
        }
        return result
    }
    configureStandardForm(passwordForm, onPasswordFormSuccess, onPasswordValidation)

    const revokeTokenForms = settingsSecurityBody.querySelectorAll("form.revoke-token-form")
    for (const form of revokeTokenForms) {
        const onRevokeTokenFormSuccess = () => {
            const row = form.closest(".active-session")
            const isCurrentSession = row.querySelector(".current-session") !== null
            if (isCurrentSession) {
                window.location = `/login?${qsEncode({ referer: window.location.pathname + window.location.search })}`
            } else {
                row.remove()
            }
        }

        configureStandardForm(form, onRevokeTokenFormSuccess)
    }
}
