import i18next from "i18next"
import { qsEncode } from "../_qs"
import { type APIDetail, configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.settings-security-body")
if (body) {
    const passwordForm = body.querySelector("form.password-form")
    const newPasswordInput = passwordForm.querySelector("input[type=password][data-name=new_password]")
    const newPasswordConfirmInput = passwordForm.querySelector("input[type=password][data-name=new_password_confirm]")

    configureStandardForm(
        passwordForm,
        () => {
            // On success callback, reset the password change form
            console.debug("onPasswordFormSuccess")
            passwordForm.reset()
        },
        () => {
            const result: APIDetail[] = []
            // Validate passwords equality
            if (newPasswordInput.value !== newPasswordConfirmInput.value) {
                const msg = i18next.t("validation.passwords_missmatch")
                result.push({ type: "error", loc: ["", "new_password"], msg })
                result.push({ type: "error", loc: ["", "new_password_confirm"], msg })
            }
            return result
        },
    )

    const revokeTokenForms = body.querySelectorAll("form.revoke-token-form")
    for (const form of revokeTokenForms) {
        configureStandardForm(form, () => {
            // On success callback, remove the HTML element or redirect to login page
            console.debug("onRevokeTokenFormSuccess")
            const row = form.closest("li")
            const isCurrentSession = row.querySelector(".current-session") !== null
            if (isCurrentSession) {
                window.location.href = `/login?${qsEncode({ referer: window.location.pathname + window.location.search })}`
            } else {
                row.remove()
            }
        })
    }
}
