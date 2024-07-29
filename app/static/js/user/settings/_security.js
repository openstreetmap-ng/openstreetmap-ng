import { qsEncode } from "../../_qs.js"
import { configureStandardForm } from "../../_standard-form.js"

const settingsSecurityBody = document.querySelector("body.settings-security-body")
if (settingsSecurityBody) {
    const revokeTokenForms = settingsSecurityBody.querySelectorAll(".revoke-token-form")
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
