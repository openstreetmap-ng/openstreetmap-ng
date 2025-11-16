import { mount } from "../lib/mount"
import { qsParse } from "../lib/qs"
import { configureStandardForm } from "../lib/standard-form"

const loginForm = document.querySelector("form.login-form")
if (loginForm) {
    const defaultReferrer = `${window.location.pathname}${window.location.search}`
    const params = qsParse(window.location.search)
    let referrer = params.referer ?? defaultReferrer
    // Referrer must start with '/' to avoid open redirect
    if (!referrer.startsWith("/")) referrer = defaultReferrer

    const totpCodeSection = loginForm.querySelector(".totp-code-section")
    const totpCodeInput = loginForm.querySelector(
        "input[name=totp_code]",
    ) as HTMLInputElement

    // On successful login (or 2FA required), handle appropriately
    configureStandardForm(
        loginForm,
        (data) => {
            // Check if 2FA is required
            if (data && typeof data === "object" && "requires_2fa" in data && data.requires_2fa) {
                console.debug("2FA required, showing code input")
                // Show TOTP code section
                totpCodeSection?.classList.remove("d-none")
                // Focus on TOTP input
                totpCodeInput?.focus()
                // Don't redirect - let user enter 2FA code
                return
            }

            // Normal login success - redirect
            console.debug("onLoginFormSuccess", referrer)
            if (referrer !== defaultReferrer) {
                window.location.href = `${window.location.origin}${referrer}`
            } else {
                window.location.reload()
            }
        },
    )

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

        const loginInput = loginForm.elements.namedItem(
            "display_name_or_email",
        ) as HTMLInputElement
        loginInput.value = dataset.login

        const passwordInput = loginForm.querySelector(
            "input[type=password][data-name=password]",
        ) as HTMLInputElement
        passwordInput.value = dataset.password

        const rememberInput = loginForm.elements.namedItem(
            "remember",
        ) as HTMLInputElement
        rememberInput.checked = true

        loginForm.requestSubmit()
    }

    const autofillButtons = document.querySelectorAll("button.autofill-btn")
    for (const btn of autofillButtons) {
        btn.addEventListener("click", onAutofillButtonClick)
    }
}

// On /login page, remove modal handling and instead reload the page
mount("login-body", () => {
    const navbarLoginButton = document.querySelector(
        "button[data-bs-target='#loginModal']",
    )
    navbarLoginButton.removeAttribute("data-bs-target")
    navbarLoginButton.removeAttribute("data-bs-toggle")
    navbarLoginButton.addEventListener("click", () => {
        window.location.reload()
    })
})
