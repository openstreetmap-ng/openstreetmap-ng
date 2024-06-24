import { configureStandardForm } from "../_standard-form.js"

const accountConfirmBody = document.querySelector("body.account-confirm-body")
if (accountConfirmBody) {
    const resendForm = accountConfirmBody.querySelector("form.resend-form")

    // On successful resend, redirect to welcome if account is already active
    const onResendFormSuccess = (data) => {
        console.debug("onResendSuccess", data)
        if (data.is_active) window.location = "/welcome"
    }

    configureStandardForm(resendForm, onResendFormSuccess)
}
