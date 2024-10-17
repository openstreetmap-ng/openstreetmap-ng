import { t } from "i18next"
import { configureStandardForm } from "../../_standard-form.js"

const onResetSecretButtonClick = ({ target }) => {
    console.debug("onResetSecretButtonClick")
    const control = target.closest(".reset-secret-control")
    const form = control.querySelector("form.reset-secret-form") ?? document.querySelector("form.reset-secret-form")
    if (confirm(t("settings.new_secret_question"))) {
        // Configure standard form if not already configured
        if (!form.classList.contains("needs-validation")) {
            const onResetSecretFormSuccess = ({ secret }) => {
                console.debug("onResetSecretFormSuccess")
                const input = target.parentElement.querySelector("input")
                input.value = secret
                input.dispatchEvent(new Event("change"))
            }

            configureStandardForm(form, onResetSecretFormSuccess)
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
            console.warn("Reset control button not found", control)
            continue
        }
        button.addEventListener("click", onResetSecretButtonClick)
    }
}
