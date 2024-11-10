import { qsParse } from "./_qs"
import { configureStandardForm } from "./_standard-form"

const loginForm = document.querySelector("form.login-form")
if (loginForm) {
    const defaultReferrer = `${window.location.pathname}${window.location.search}`
    const params = qsParse(window.location.search.substring(1))
    let referrer = params.referer ?? defaultReferrer
    // Referrer must start with '/' to avoid open redirect
    if (!referrer.startsWith("/")) referrer = defaultReferrer

    // On successful login, redirect to refer
    configureStandardForm(loginForm, () => {
        console.debug("onLoginFormSuccess", referrer)
        if (referrer !== defaultReferrer) {
            window.location.href = `${window.location.origin}${referrer}`
        } else {
            window.location.reload()
        }
    })

    // Propagate referer to auth providers forms
    const authProvidersForms = document.querySelectorAll(".auth-providers form")
    for (const form of authProvidersForms) {
        const referrerInput = form.elements.namedItem("referer") as HTMLInputElement
        if (referrerInput) referrerInput.value = referrer
    }

    // Autofill buttons are present in development environment
    const onAutofillButtonClick = ({ target }: Event): void => {
        const dataset = (target as HTMLButtonElement).dataset
        console.debug("onAutofillButtonClick", dataset)
        ;(loginForm.elements.namedItem("display_name_or_email") as HTMLInputElement).value = dataset.login
        loginForm.querySelector("input[type=password][data-name=password]").value = dataset.password
        ;(loginForm.elements.namedItem("remember") as HTMLInputElement).checked = true
        loginForm.requestSubmit()
    }

    const autofillButtons = document.querySelectorAll("button.autofill-btn")
    for (const loginButton of autofillButtons) {
        loginButton.addEventListener("click", onAutofillButtonClick)
    }
}

// On /login page, remove modal handling and instead reload the page
const loginBody = document.querySelector("body.login-body")
if (loginBody) {
    const navbarLoginButton = document.querySelector("button[data-bs-target='#loginModal']")
    navbarLoginButton.removeAttribute("data-bs-target")
    navbarLoginButton.removeAttribute("data-bs-toggle")
    navbarLoginButton.addEventListener("click", () => {
        window.location.reload()
    })
}
