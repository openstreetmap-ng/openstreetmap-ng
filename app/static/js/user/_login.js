import { qsParse } from "../_qs.js"
import { configureStandardForm } from "../_standard-form.js"

const loginBody = document.querySelector("body.login-body")
if (loginBody) {
    const loginForm = loginBody.querySelector("form.login-form")
    const loginInputs = loginForm.elements
    const autofillButtons = loginBody.querySelectorAll("button[data-login][data-password]")

    const onLoginSuccess = () => {
        // Redirect to refer from query string and hash
        // Referrer must start with '/' to avoid open redirect
        const params = qsParse(location.search.substring(1))
        let referer = (params.referer ?? "/") + location.hash
        if (!referer.startsWith("/")) referer = "/"
        window.location = referer
    }

    // Autofill buttons are present in development environment
    const onAutofillButtonClick = (e) => {
        const dataset = e.target.dataset
        console.debug("onAutofillButtonClick", dataset)
        loginInputs.display_name_or_email.value = dataset.login
        loginInputs.password.value = dataset.password
        loginInputs.remember.checked = true
        loginForm.requestSubmit()
    }

    // Listen for events
    configureStandardForm(loginForm, onLoginSuccess)
    for (const loginButton of autofillButtons) {
        loginButton.addEventListener("click", onAutofillButtonClick)
    }
}
