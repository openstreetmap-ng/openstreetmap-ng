import { qsParse } from "./_qs"
import { configureStandardForm } from "./_standard-form"

const loginForm = document.querySelector("form.login-form")
if (loginForm) {
    configureStandardForm(loginForm, () => {
        // Redirect to refer from query string and hash
        // Referrer must start with '/' to avoid open redirect
        const currentPath = window.location.pathname
        const params = qsParse(window.location.search.substring(1))
        let referer = params.referer ?? currentPath
        if (!referer.startsWith("/")) referer = currentPath
        console.debug("onLoginFormSuccess", referer)
        if (referer !== currentPath) {
            window.location.pathname = referer
        } else {
            window.location.reload()
        }
    })

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
