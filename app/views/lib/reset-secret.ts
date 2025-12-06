import { configureStandardForm } from "@lib/standard-form"
import { t } from "i18next"

const onResetSecretButtonClick = (event: Event) => {
    console.debug("onResetSecretButtonClick")
    const button = event.target as HTMLButtonElement
    const control = button.closest(".reset-secret-control")
    const form =
        control?.querySelector("form.reset-secret-form") ??
        document.querySelector("form.reset-secret-form")!

    if (confirm(t("settings.new_secret_question"))) {
        configureStandardForm(form, ({ secret }) => {
            // On success callback, display the new secret
            console.debug("onResetSecretFormSuccess")
            const input = button.parentElement!.querySelector("input")!
            input.value = secret
            input.dispatchEvent(new Event("change"))
        })
        form.requestSubmit()
    }
}

for (const control of document.querySelectorAll(".reset-secret-control")) {
    const button = control.querySelector("button.reset-secret-btn")
    if (button) {
        button.addEventListener("click", onResetSecretButtonClick)
    } else {
        console.error("Reset control button is not available", control)
    }
}
