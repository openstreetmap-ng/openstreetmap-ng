import { configureStandardForm } from "../_standard-form.js"

const accountConfirmBody = document.querySelector("body.account-confirm-body")
if (accountConfirmBody) {
    const resendForm = accountConfirmBody.querySelector("form.resend-form")

    const onResendSuccess = (data) => {
        console.debug("onResendSuccess", data)
        if (data.is_active) location = "/welcome"
    }

    configureStandardForm(resendForm, onResendSuccess)
}
