import { t } from "i18next"
import { configureStandardForm } from "../../_standard-form"

const onResetSecretButtonClick = (event: Event) => {
    const target = event.target as HTMLButtonElement
    console.debug("onResetSecretButtonClick")
    const control = target.closest(".reset-secret-control")
    const form = control.querySelector("form.reset-secret-form") ?? document.querySelector("form.reset-secret-form")

    if (confirm(t("settings.new_secret_question"))) {
        // Configure standard form if not already configured
        if (!form.classList.contains("needs-validation")) {
            configureStandardForm(form, ({ secret }) => {
                // On success callback, display the new secret
                console.debug("onResetSecretFormSuccess")
                const input = target.parentElement.querySelector("input")
                input.value = secret
                input.dispatchEvent(new Event("change"))
            })
        }
        form.requestSubmit()
    }
}

export const initializeResetSecretControls = () => {
    const resetSecretControls = document.querySelectorAll(".reset-secret-control")
    console.debug("Initializing", resetSecretControls.length, "reset secret controls")
    for (const control of resetSecretControls) {
        const button = control.querySelector("button.reset-secret-button")
        if (!button) {
            console.error("Reset control button is not available", control)
            continue
        }
        button.addEventListener("click", onResetSecretButtonClick)
    }
}
