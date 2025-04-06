import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.account-confirm-body")
if (body) {
    configureStandardForm(body.querySelector("form.resend-form"), (data) => {
        // On successful resend, redirect to welcome if account is already active
        console.debug("onResendSuccess", data)
        if (data.is_active) window.location.href = "/welcome"
    })
}
