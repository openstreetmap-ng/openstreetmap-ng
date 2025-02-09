import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.messages-new-body")
if (body) {
    const messageForm = body.querySelector("form.message-form")
    configureStandardForm(messageForm, ({ redirect_url }) => {
        console.debug("onMessageFormSuccess", redirect_url)
        window.location.href = redirect_url
    })

    const messageBody = messageForm.elements.namedItem("body") as HTMLTextAreaElement
    if (messageBody.value) {
        // When body is present, autofocus at the beginning
        messageBody.focus()
        messageBody.setSelectionRange(0, 0)
    }
}
