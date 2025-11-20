import { mount } from "../lib/mount"
import { configureStandardForm } from "../lib/standard-form"

mount("messages-new-body", (body) => {
    const messageForm = body.querySelector("form.message-form")
    configureStandardForm(messageForm, ({ redirect_url }) => {
        console.debug("onMessageFormSuccess", redirect_url)
        window.location.href = redirect_url
    })

    const messageBody = messageForm.querySelector("textarea[name=body]")
    if (messageBody.value) {
        // When body is present, autofocus at the beginning
        messageBody.focus()
        messageBody.setSelectionRange(0, 0)
    }
})
