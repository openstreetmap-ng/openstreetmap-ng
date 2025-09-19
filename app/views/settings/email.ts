import { mount } from "../lib/mount"
import { configureStandardForm } from "../lib/standard-form"

mount("settings-email-body", (body) => {
    const emailForm = body.querySelector("form.email-form")
    configureStandardForm(emailForm, () => {
        // On success callback, reset the email change form
        emailForm.reset()
    })
})
