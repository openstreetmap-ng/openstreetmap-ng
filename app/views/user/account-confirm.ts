import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"

mount("account-confirm-body", (body) => {
    configureStandardForm(body.querySelector("form.resend-form"), (data) => {
        // On successful resend, redirect to welcome if account is already active
        console.debug("onResendSuccess", data)
        if (data.is_active) window.location.href = "/welcome"
    })
})
