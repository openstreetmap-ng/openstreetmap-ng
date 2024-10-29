import { qsParse } from "../_qs"
import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.login-body")
if (body) {
    const loginForm = body.querySelector("form.login-form")
    configureStandardForm(loginForm, () => {
        // Redirect to refer from query string and hash
        // Referrer must start with '/' to avoid open redirect
        const params = qsParse(window.location.search.substring(1))
        let referer = (params.referer ?? "/") + window.location.hash
        if (!referer.startsWith("/")) referer = "/"
        window.location.href = referer
    })

    // Autofill buttons are present in development environment
    const loginInputs = loginForm.elements
    const onAutofillButtonClick = ({ target }: Event): void => {
        const dataset = (target as HTMLButtonElement).dataset
        console.debug("onAutofillButtonClick", dataset)
        ;(loginInputs.namedItem("display_name_or_email") as HTMLInputElement).value = dataset.login
        ;(loginInputs.namedItem("password") as HTMLInputElement).value = dataset.password
        ;(loginInputs.namedItem("remember") as HTMLInputElement).checked = true
        loginForm.requestSubmit()
    }

    const autofillButtons = body.querySelectorAll("button[data-login][data-password]")
    for (const loginButton of autofillButtons) {
        loginButton.addEventListener("click", onAutofillButtonClick)
    }
}
