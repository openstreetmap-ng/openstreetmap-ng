import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.account-confirm-body")
if (body) {
    const resendForm = body.querySelector("form.resend-form")
    configureStandardForm(resendForm, (data) => {
        // On successful resend, redirect to welcome if account is already active
        console.debug("onResendSuccess", data)
        if (data.is_active) window.location.href = "/welcome"
    })
}
