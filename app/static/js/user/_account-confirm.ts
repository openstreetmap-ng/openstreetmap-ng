import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.account-confirm-body")
if (body) {
    const resendForm: HTMLFormElement = body.querySelector("form.resend-form")

    // On successful resend, redirect to welcome if account is already active
    configureStandardForm(resendForm, (data) => {
        console.debug("onResendSuccess", data)
        if (data.is_active) window.location.href = "/welcome"
    })
}
